import base64
import sys
from diffusers import StableDiffusionXLPipeline, StableDiffusionXLImg2ImgPipeline
import torch
import argparse
from dotenv import load_dotenv
import os
import asyncio
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from diffusers.utils import logging
import io
import json


DEFALUT_MODEL = ""

load_dotenv()
server = Server("image-generator-server")
pipe = None
img2img_pipe = None
default_negative_prompt = None
output_base_path = None

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """利用可能なツールのリストを返す"""
    return [
        Tool(
            name="generate_image",
            description="プロンプトから画像を生成します",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "画像生成用のプロンプトテキスト",
                    },
                    "negative_prompt": {
                        "type": "string",
                        "description": "ネガティブプロンプト（オプション）",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "出力ベースパス（オプション）",
                    },
                    "steps": {
                        "type": "integer",
                        "description": "推論ステップ数（デフォルト: 40）",
                    },
                },
                "required": ["prompt"],
            },
        ),
        Tool(
            name="image2image",
            description="入力画像をプロンプトに基づいて変換します（image-to-image）",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "画像変換用のプロンプトテキスト",
                    },
                    "image_path": {
                        "type": "string",
                        "description": "変換元の画像パス（Base64またはファイルパス）",
                    },
                    "negative_prompt": {
                        "type": "string",
                        "description": "ネガティブプロンプト（オプション）",
                    },
                    "strength": {
                        "type": "number",
                        "description": "変換強度 (0.0-1.0)。値が大きいほど元の画像から変化します（デフォルト: 0.2）",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "出力ベースパス（オプション）",
                    },
                    "steps": {
                        "type": "integer",
                        "description": "推論ステップ数（デフォルト: 40）",
                    },
                },
                "required": ["prompt", "image_path"],
            },
        ),
    ]

# ツールの呼び出し処理
@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    """ツールを実行して結果を返す"""
    if name == "generate_image":
        return await handle_generate_image(name, arguments)
    elif name == "image2image":
        return await handle_image2image(name, arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")

async def handle_generate_image(name: str, arguments: dict) -> list[TextContent]:
    """generate_imageツールを実行して結果を返す"""
    # パラメータの取得
    prompt = arguments.get("prompt", "").strip()
    negative_prompt = arguments.get("negative_prompt", default_negative_prompt)
    steps = arguments.get("steps", 40)

    # 空のプロンプトチェック
    if not prompt:
        return [TextContent(
            type="text",
            text="エラー: プロンプトが空です"
        )]

    try:
        client_provided_output_path = arguments.get("output_path")

        if client_provided_output_path:
            # クライアントが出力パスを指定した場合、そのパスに画像を保存してパスを返す
            image_path = generate_and_save_image(
                pipe,
                prompt,
                negative_prompt,
                output_base_path=client_provided_output_path,
                prefix_message="MCP",
                output="path",
                num_inference_steps=steps,
            )

            if image_path:
                return [
                    TextContent(
                    type="text",
                    text=json.dumps({
                        "success": True,
                        "output": image_path,
                    })
                    )
                ]
            else:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({
                            "success": False,
                            "message": f"画像の生成または指定されたパス '{client_provided_output_path}' への保存に失敗しました。",
                        })
                    )
                ]
        else:
            # クライアントが出力パスを指定しなかった場合、画像を生成して base64 で返す
            base64_image = generate_and_save_image(
                pipe,
                prompt,
                negative_prompt,
                output_base_path=output_base_path,
                prefix_message="MCP",
                output="base64",
                num_inference_steps=steps,
            )
            
            if base64_image:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({
                            "success": True,
                            "output": base64_image,
                        })
                    )
                ]
            else:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({
                            "success": False,
                            "message": "Base64 画像の生成に失敗しました。",
                        })
                    )
                ]
    
    except Exception as e:
        error_msg = f"画像生成中にエラーが発生しました: {str(e)}"
        return [TextContent(
            type="text",
            text=error_msg
        )]

async def handle_image2image(name: str, arguments: dict) -> list[TextContent]:
    """image2imageツールを実行して結果を返す"""
    from PIL import Image
    import base64
    
    # パラメータの取得
    prompt = arguments.get("prompt", "").strip()
    image_path = arguments.get("image_path", "").strip()
    negative_prompt = arguments.get("negative_prompt", default_negative_prompt)
    strength = arguments.get("strength", 0.1)
    steps = arguments.get("steps", 40)
    client_provided_output_path = arguments.get("output_path")
    
    # パラメータチェック
    if not prompt:
        return [TextContent(
            type="text",
            text="エラー: プロンプトが空です"
        )]
    
    if not image_path:
        return [TextContent(
            type="text",
            text="エラー: 画像パスが空です"
        )]
    
    # 画像を読み込み（Base64またはファイルパス）
    try:
        if image_path.startswith("data:image") or "," in image_path:
            # Base64画像の場合
            if "," in image_path:
                base64_data = image_path.split(",", 1)[1]
            else:
                base64_data = image_path
            img_bytes = base64.b64decode(base64_data)
            input_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        else:
            # ファイルパスの場合
            input_image = Image.open(image_path).convert("RGB")
    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "message": f"画像の読み込みに失敗しました: {str(e)}",
            })
        )]
    
    try:
        # image2imgパイプラインが初期化されていない場合は初期化
        global img2img_pipe
        if img2img_pipe is None and pipe is not None:
            img2img_pipe = StableDiffusionXLImg2ImgPipeline.from_pipe(pipe)
            img2img_pipe.to(pipe.device)
        
        if img2img_pipe is None:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "message": "img2imgパイプラインが初期化されていません",
                })
            )]
        
        # プログレスバーを無効化
        img2img_pipe.set_progress_bar_config(disable=True)
        
        # 画像変換
        result = img2img_pipe(
            prompt=prompt,
            image=input_image,
            negative_prompt=negative_prompt,
            strength=strength,
            num_inference_steps=steps,
        )

        output_image = result.images[0]

        if client_provided_output_path:
            # クライアントが出力パスを指定した場合、そのパスに画像を保存
            output_path = unique_path(client_provided_output_path)
            output_image.save(output_path)
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "output": output_path,
                })
            )]
        else:
            # Base64で返す
            buffered = io.BytesIO()
            output_image.save(buffered, format="PNG")
            img_bytes = buffered.getvalue()
            base64_image = base64.b64encode(img_bytes).decode('utf-8')
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "output": base64_image,
                })
            )]
    
    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "message": f"image2image中にエラーが発生しました: {str(e)}",
            })
        )]

def set_server_config(diffusion_pipe, neg_prompt: str, output_path: str):
    """サーバーの設定を初期化"""
    global pipe, default_negative_prompt, output_base_path
    pipe = diffusion_pipe
    default_negative_prompt = neg_prompt
    output_base_path = output_path

# サーバーの起動
async def run_mcp_server():
    """MCPサーバーを起動"""
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="image-generator-server",
                    server_version="0.1.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
    except KeyboardInterrupt:
        print("MCP mode interrupted by user. Exiting.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"MCP mode encountered an unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

def run_mcp_mode(diffusion_pipe, args, base_output_path):
    """
    MCP モードでサーバーを起動
    
    Args:
        diffusion_pipe: 画像生成パイプライン
        args: コマンドライン引数（negative_promptを含む）
        base_output_path: 出力ベースパス
    """
    # サーバー設定を初期化
    set_server_config(
        diffusion_pipe,
        args.negative_prompt,
        base_output_path
    )
    
    # 非同期サーバーを起動
    try:
        asyncio.run(run_mcp_server())
    except KeyboardInterrupt:
        print("MCP mode interrupted by user. Exiting.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"MCP mode encountered an unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

def ensure_dir(path):
    dir_name = os.path.dirname(path) or "."
    os.makedirs(dir_name, exist_ok=True)
    return dir_name

def unique_path(path):
    dir_name = ensure_dir(path)
    base = os.path.basename(path)
    root, ext = os.path.splitext(base)
    candidate = os.path.join(dir_name, base)
    i = 1
    while os.path.exists(candidate):
        candidate = os.path.join(dir_name, f"{root} ({i}){ext}")
        i += 1
    return candidate

def load_pipeline(model_id, device="cuda", mode="default"):
    # Set torch_dtype conditionally based on the device
    dtype_args = {
        "use_safetensors": True,
        "torch_dtype": torch.float16
    }

    if device == "cpu":
        dtype_args["torch_dtype"] = torch.float32

    if os.path.exists(model_id):
        if os.path.isfile(model_id):
            old_stderr = sys.stderr
            if mode == "mcp":
                sys.stderr = io.StringIO()
            
            pipe = StableDiffusionXLPipeline.from_single_file(
                model_id,
                **dtype_args
            )
            if mode == "mcp":
                sys.stderr = old_stderr
            pipe.to(device)
        else:
            pipe = StableDiffusionXLPipeline.from_pretrained(
                model_id,
                **dtype_args
            )
            pipe.to(device)
    else:
        pipe = StableDiffusionXLPipeline.from_pretrained(
            model_id,
            **dtype_args
        )
        pipe.to(device)
    return pipe

def save_images(pipe, prompt, negative_prompt, output_path, num_images=1, num_inference_steps=40):
    dir_name = ensure_dir(output_path)
    base = os.path.basename(output_path)
    root, ext = os.path.splitext(base)

    saved_paths = []
    first_path = unique_path(output_path)
    for idx in range(num_images):
        out_path = first_path if idx == 0 else unique_path(os.path.join(dir_name, f"{root} ({idx}){ext}"))
        result = pipe(prompt, negative_prompt=negative_prompt, num_inference_steps=num_inference_steps)
        image = result.images[0]
        image.save(out_path)
        saved_paths.append(out_path)
    return saved_paths

def generate_and_save_image(pipe, prompt, negative_prompt, output_base_path="images/output.png", prefix_message="", output="path", num_inference_steps=20):
    """Generates a single image and saves it to a unique path."""
    if prefix_message == "MCP":
        pipe.set_progress_bar_config(disable=True)

    try:
        result = pipe(prompt, negative_prompt=negative_prompt, num_inference_steps=num_inference_steps)
        for image in result.images:
            path = output_base_path
            if output_base_path:
                try:
                    path = unique_path(output_base_path)
                except KeyboardInterrupt:
                    print(f"{prefix_message} interrupted by user. Exiting.", file=sys.stderr)
                    sys.exit(1)
            
            if output == "base64":
                buffered = io.BytesIO()
                image.save(buffered, format="PNG")  # または "JPEG" など
                img_bytes = buffered.getvalue()
                return base64.b64encode(img_bytes).decode('utf-8')

            image.save(path)
            return path
    except Exception as e:
        print(f"{prefix_message} Error generating image for prompt '{prompt}': {e}", file=sys.stderr)
    return None

def run_img2img_mode(pipe, args, output_base_path):
    """Handles image2image in normal mode."""
    from PIL import Image

    # 入力画像を読み込み
    try:
        input_image = Image.open(args.input_image).convert("RGB")
    except Exception as e:
        print(f"❌  入力画像の読み込みに失敗しました: {e}", file=sys.stderr)
        sys.exit(1)
    
    # img2imgパイプラインを初期化
    print(f"{pipe.device} を使用します")
    print("img2img パイプラインを読み込んでいます...")
    img2img_pipe = StableDiffusionXLImg2ImgPipeline.from_pipe(pipe)
    img2img_pipe.to(pipe.device)
    
    print(f"次のプロンプトで画像を変換: '{args.prompt}'")
    print(f"入力画像: {args.input_image}")
    print(f"変換強度: {args.strength}")
    print(f"推論ステップ数: {args.steps}")

    # 画像変換
    result = img2img_pipe(
        prompt=args.prompt,
        image=input_image,
        negative_prompt=args.negative_prompt,
        strength=args.strength,
        num_inference_steps=args.steps,
    )
    
    output_image = result.images[0]
    path = unique_path(output_base_path)
    output_image.save(path)
    print(f"変換画像: {path}")
    return path

def run_normal_mode(pipe, args, output_base_path, parser):
    """Handles image generation in normal mode."""

    print(f"次のプロンプトによって生成される {args.num_images} 枚の画像: '{args.prompt}'")
    print(f"推論ステップ数: {args.steps}")
    for _ in range(args.num_images):
        path = generate_and_save_image(
            pipe,
            args.prompt,
            args.negative_prompt,
            output=output_base_path,
            prefix_message="Normal mode",
            num_inference_steps=args.steps,
        )
        if path:
            print(f"生成画像: {path}")

def main():
    parser = argparse.ArgumentParser(description="Stable Diffusion XL を使用して画像を生成します。")
    for action in parser._actions:
        if isinstance(action, argparse._HelpAction):
            action.help = "このヘルプメッセージを表示してプログラムを終了します。"
            break
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0", help="プログラムのバージョン (0.1.0) を表示して終了します。")
    parser.add_argument("--mcp", action="store_true",
            help="Multi Client Protocol (MCP) モードを有効にします。")
    parser.add_argument("--img2img", action="store_true",
            help="image2image モードを有効にします。入力画像をプロンプトに基づいて変換します。")
    parser.add_argument("--input-image", "-i", type=str, default=None,
            help="image2image の入力画像パス (image2image モード必須)")
    parser.add_argument("--strength", "-s", type=float, default=0.1,
            help="image2image の変換強度 0.0-1.0 (デフォルト: 0.1)")
    parser.add_argument("prompt", type=str, nargs='?',
            help="画像生成のためのプロンプト (通常モードは必須、MCP モードでは標準入力から読み込み)")
    default_model = os.getenv("MODEL", DEFALUT_MODEL)
    parser.add_argument("--model-id", "-m", type=str, default=default_model,
            help=f"Stable Diffusion のモデル ID")
    parser.add_argument("--negative-prompt", "-np", type=str, default=None,
            help="画像生成のためのネガティブプロンプト (オプション)")
    parser.add_argument("--output", "-o", type=str, default="images/output.png",
            help="生成された画像の出力ファイル名 (デフォルト: output.png)")
    parser.add_argument("--num-images", "-n", type=int, default=1,
            help="生成する画像の数 (デフォルト: 1、通常モードのみ)")
    parser.add_argument("--steps", type=int, default=40,
            help="推論ステップ数 (デフォルト: 40)")
    args = parser.parse_args()

    # モデルロード前に全引数を検証
    if not args.model_id:
        print("❌  モデル ID (--model-id オプションまたは MODEL 環境変数) が指定されていません。", file=sys.stderr)
        sys.exit(1)

    if args.prompt is None and not args.mcp:
        print("❌  通常モードでは prompt 引数が必要です。詳細については --help を使用してください。", file=sys.stderr)
        sys.exit(1)

    if args.img2img and not args.input_image:
        print("❌  image2image モードでは --input-image オプションが必要です。", file=sys.stderr)
        sys.exit(1)

    if args.img2img and args.input_image and not os.path.exists(args.input_image):
        print(f"❌  入力画像ファイルが見つかりません: {args.input_image}", file=sys.stderr)
        sys.exit(1)

    # 出力ファイルの準備（ユニーク化はループ内で行う）
    output_base_path = args.output
    ensure_dir(output_base_path)

    # モデルロード（GPUがなければCPUへフォールバック）
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_id = args.model_id

    # ローカルパスと判断できる場合（絶対パス・相対パス・拡張子あり）は存在確認
    is_local_path = (
        os.path.isabs(model_id)
        or model_id.startswith(("./", ".\\", "../", "..\\"))
        or bool(os.path.splitext(model_id)[1])
    )
    if is_local_path and not os.path.exists(model_id):
        print(f"❌  モデルが見つかりません: {model_id}", file=sys.stderr)
        sys.exit(1)

    if args.mcp:
        logging.disable_progress_bar()
        try:
            pipe: StableDiffusionXLPipeline = load_pipeline(model_id, device=device, mode="mcp")
        except Exception as e:
            print(f"❌  モデルの読み込みに失敗しました: {e}", file=sys.stderr)
            sys.exit(1)
        run_mcp_mode(pipe, args, output_base_path)
    elif args.img2img:
        print(f"{device} を使用します")
        print(f"{model_id} を読み込んでいます...")
        try:
            pipe: StableDiffusionXLPipeline = load_pipeline(model_id, device=device)
        except Exception as e:
            print(f"❌  モデルの読み込みに失敗しました: {e}", file=sys.stderr)
            sys.exit(1)
        run_img2img_mode(pipe, args, output_base_path)
    else:
        print(f"{device} を使用します")
        print(f"{model_id} を読み込んでいます...")
        try:
            pipe: StableDiffusionXLPipeline = load_pipeline(model_id, device=device)
        except Exception as e:
            print(f"❌  モデルの読み込みに失敗しました: {e}", file=sys.stderr)
            sys.exit(1)
        run_normal_mode(pipe, args, output_base_path, parser)
    
if __name__ == "__main__":
    main()
