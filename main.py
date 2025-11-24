import sys
from diffusers import StableDiffusionXLPipeline
import torch
import argparse
from dotenv import load_dotenv
import os
load_dotenv()

DEFALUT_MODEL = ""

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

def load_pipeline(model_id, device="cuda"):
    if os.path.exists(model_id):
        if os.path.isfile(model_id):
            pipe = StableDiffusionXLPipeline.from_single_file(
                model_id,
                torch_dtype=torch.float16,
                use_safetensors=True,
            )
            pipe.to(device)
        else:
            pipe = StableDiffusionXLPipeline.from_pretrained(
                model_id,
                torch_dtype=torch.float16,
                use_safetensors=True,
            )
            pipe.to(device)
    else:
        pipe = StableDiffusionXLPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16,
            use_safetensors=True
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

def generate_and_save_image(pipe, prompt, negative_prompt, output_base_path, prefix_message=""):
    """Generates a single image and saves it to a unique path."""
    try:
        result = pipe(prompt, negative_prompt=negative_prompt)
        for image in result.images:
            try:
                path = unique_path(output_base_path)
            except KeyboardInterrupt:
                print(f"{prefix_message} interrupted by user. Exiting.", file=sys.stderr)
                sys.exit(1)
            image.save(path)
            return path
    except Exception as e:
        print(f"{prefix_message} Error generating image for prompt '{prompt}': {e}", file=sys.stderr)
    return None

def run_mcp_mode(pipe, args, output_base_path):
    """Handles image generation in Multi-Client Protocol mode."""
    print("Entering MCP mode. Send prompts via stdin (one per line). Output paths to stdout.", file=sys.stderr)
    try:
        for line_num, line in enumerate(sys.stdin):
            current_prompt = line.strip()
            if not current_prompt:
                print(f"MCP: Skipping empty line {line_num+1}.", file=sys.stderr)
                continue

            print(f"MCP: Processing line {line_num+1} with prompt: '{current_prompt}'", file=sys.stderr)
            path = generate_and_save_image(
                pipe,
                current_prompt,
                args.negative_prompt,
                output_base_path,
                prefix_message="MCP"
            )
            if path:
                print(path) # Output generated path to stdout for the MCP client
    except KeyboardInterrupt:
        print("MCP mode interrupted by user. Exiting.", file=sys.stderr)
        sys.exit(1)

def run_normal_mode(pipe, args, output_base_path):
    """Handles image generation in normal mode."""
    if args.prompt is None:
        parser.error("The 'prompt' argument is required in normal mode. Use --help for more information.")

    print(f"Generating {args.num_images} images for prompt: '{args.prompt}'", file=sys.stderr)
    for i in range(args.num_images):
        path = generate_and_save_image(
            pipe,
            args.prompt,
            args.negative_prompt,
            output_base_path,
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
    print(f"Loading model {model_id} to {device}...", file=sys.stderr)
    pipe: StableDiffusionXLPipeline = load_pipeline(model_id, device=device)

    if args.mcp:
        run_mcp_mode(pipe, args, output_base_path)
    else:
        run_normal_mode(pipe, args, output_base_path)
    
if __name__ == "__main__":
    main()
