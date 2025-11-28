import base64
import sys
from diffusers import StableDiffusionXLPipeline
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
                },
                "required": ["prompt"],
            },
        ),
    ]

# ツールの呼び出し処理
@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    """ツールを実行して結果を返す"""
    if name != "generate_image":
        raise ValueError(f"Unknown tool: {name}")
    
    # パラメータの取得
    prompt = arguments.get("prompt", "").strip()
    negative_prompt = arguments.get("negative_prompt", default_negative_prompt)
    output_path = arguments.get("output_path", output_base_path)
    
    # 空のプロンプトチェック
    if not prompt:
        return [TextContent(
            type="text",
            text="エラー: プロンプトが空です"
        )]
    
    try:        
        base64_image = generate_and_save_image(
            pipe,
            prompt,
            negative_prompt,
            output_path,
            prefix_message="MCP",
            output="base64"
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
                        "message": prompt
                    })
                )
            ]
    
    except Exception as e:
        error_msg = f"画像生成中にエラーが発生しました: {str(e)}"
        return [TextContent(
            type="text",
            text=error_msg
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
    if device == "cpu":
        dtype_args = {}
    else:
        dtype_args = {"torch_dtype": torch.float16}

    if os.path.exists(model_id):
        if os.path.isfile(model_id):
            old_stderr = sys.stderr
            if mode == "mcp":
                sys.stderr = io.StringIO()
            pipe = StableDiffusionXLPipeline.from_single_file(
                model_id,
                use_safetensors=True,
                **dtype_args
            )
            if mode == "mcp":
                sys.stderr = old_stderr
            pipe.to(device)
        else:
            pipe = StableDiffusionXLPipeline.from_pretrained(
                model_id,
                use_safetensors=True,
                **dtype_args
            )
            pipe.to(device)
    else:
        pipe = StableDiffusionXLPipeline.from_pretrained(
            model_id,
            use_safetensors=True,
            **dtype_args
        )
        pipe.to(device)
    return pipe

def save_images(pipe, prompt, negative_prompt, output_path, num_images=1):
    dir_name = ensure_dir(output_path)
    base = os.path.basename(output_path)
    root, ext = os.path.splitext(base)

    saved_paths = []
    # 既に output_path はユニークなので最初はそれを使う
    first_path = unique_path(output_path) # Corrected typo _unique_path to unique_path
    for idx in range(num_images):
        out_path = first_path if idx == 0 else unique_path(os.path.join(dir_name, f"{root} ({idx}){ext}")) # Corrected typo
        result = pipe(prompt, negative_prompt=negative_prompt)
        image = result.images[0]
        image.save(out_path)
        saved_paths.append(out_path)
    return saved_paths

def generate_and_save_image(pipe, prompt, negative_prompt, output_base_path="images/output.png", prefix_message="", output="path"):
    """Generates a single image and saves it to a unique path."""
    if prefix_message == "MCP":
        pipe.set_progress_bar_config(disable=True)

    try:
        result = pipe(prompt, negative_prompt=negative_prompt)
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

def run_normal_mode(pipe, args, output_base_path, parser):
    """Handles image generation in normal mode."""
    if args.prompt is None:
        parser.error("The 'prompt' argument is required in normal mode. Use --help for more information.")

    print(f"Generating {args.num_images} images for prompt: '{args.prompt}'", file=sys.stderr)
    for i in range(args.num_images):
        path = generate_and_save_image(
            pipe,
            args.prompt,
            args.negative_prompt,
            output=output_base_path,
            prefix_message="Normal mode"
        )
        if path:
            print(f"Generated image: {path}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description="Generate an image using Stable Diffusion.")
    parser.add_argument("--mcp", action="store_true",
            help="Enable Multi-Client Protocol mode. Prompts are read from stdin, output paths to stdout.")
    parser.add_argument("prompt", type=str, nargs='?',
            help="Prompt for image generation (required in normal mode, read from stdin in MCP mode).")
    default_model = os.getenv("MODEL", DEFALUT_MODEL)
    parser.add_argument("--model-id", "-m", type=str, default=default_model,
            help=f"Model ID for Stable Diffusion (default: {default_model}).")
    parser.add_argument("--negative-prompt", "-np", type=str, default=None,
            help="Negative prompt for image generation (default: None).")
    parser.add_argument("--output", "-o", type=str, default="images/output.png",
            help="Output file name for the generated image (default: output.png).")
    parser.add_argument("--num-images", "-n", type=int, default=1,
            help="Number of images to generate (default: 1, ignored in MCP mode per prompt).")
    args = parser.parse_args()

    # 出力ファイルの準備（ユニーク化はループ内で行う）
    output_base_path = args.output
    ensure_dir(output_base_path)

    # モデルロード（GPUがなければCPUへフォールバック）
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_id = args.model_id

    if args.mcp:
        logging.disable_progress_bar()
        pipe: StableDiffusionXLPipeline = load_pipeline(model_id, device=device, mode="mcp")
        run_mcp_mode(pipe, args, output_base_path)
    else:
        print(f"Loading model {model_id} to {device}...", file=sys.stderr)
        pipe: StableDiffusionXLPipeline = load_pipeline(model_id, device=device)
        run_normal_mode(pipe, args, output_base_path, parser)
    
if __name__ == "__main__":
    main()
