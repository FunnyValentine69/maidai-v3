"""Generate animated GIF of Sakura using AnimateDiff.

Creates a subtle idle animation (breathing, hair sway) from Sakura's
static character image and saves it as a looping GIF for the GitHub README.

Usage:
    python -m sakura.animate              # Default from sakura.png
    python -m sakura.animate --force      # Regenerate even if exists
    python -m sakura.animate --seed 123   # Custom seed
    python -m sakura.animate --image assets/cache/happy.png  # Custom source
"""

import argparse
import logging
import os
import shutil
import subprocess

os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

import torch
from diffusers import AnimateDiffVideoToVideoPipeline, DDIMScheduler, MotionAdapter
from diffusers.utils import load_image
from PIL import Image
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from .config import (
    ANIMATE_BASE_MODEL,
    ANIMATE_FPS,
    ANIMATE_GUIDANCE_SCALE,
    ANIMATE_HEIGHT,
    ANIMATE_MOTION_ADAPTER,
    ANIMATE_NUM_FRAMES,
    ANIMATE_NUM_STEPS,
    ANIMATE_OUTPUT,
    ANIMATE_SEED,
    ANIMATE_SOURCE,
    ANIMATE_STRENGTH,
    ANIMATE_VAE,
    ANIMATE_WIDTH,
    IMAGE_DEVICE,
)

logger = logging.getLogger(__name__)
console = Console()

PROMPT = (
    "1girl, anime, maid outfit, pink hair, twin tails, "
    "gentle breathing, slight hair movement, soft breeze, "
    "idle animation, masterpiece, best quality"
)

NEGATIVE_PROMPT = (
    "motion blur, fast movement, walking, running, "
    "worst quality, low quality, deformed, extra limbs"
)

MAX_GIF_SIZE = 10 * 1024 * 1024  # 10MB GitHub limit


def load_pipeline(device: str) -> AnimateDiffVideoToVideoPipeline:
    """Load AnimateDiff video-to-video pipeline with MPS optimizations."""
    console.print(f"[dim]Loading motion adapter: {ANIMATE_MOTION_ADAPTER}...[/dim]")
    adapter = MotionAdapter.from_pretrained(
        ANIMATE_MOTION_ADAPTER, torch_dtype=torch.float16
    )

    console.print(f"[dim]Loading base model: {ANIMATE_BASE_MODEL}...[/dim]")
    pipe = AnimateDiffVideoToVideoPipeline.from_pretrained(
        ANIMATE_BASE_MODEL,
        motion_adapter=adapter,
        torch_dtype=torch.float16,
    )

    # Use recommended VAE for better color reproduction
    from diffusers import AutoencoderKL

    console.print(f"[dim]Loading VAE: {ANIMATE_VAE}...[/dim]")
    vae = AutoencoderKL.from_pretrained(ANIMATE_VAE, torch_dtype=torch.float16)
    pipe.vae = vae

    pipe.scheduler = DDIMScheduler.from_pretrained(
        ANIMATE_BASE_MODEL,
        subfolder="scheduler",
        clip_sample=False,
        timestep_spacing="linspace",
        beta_schedule="linear",
        steps_offset=1,
    )

    pipe = pipe.to(device)

    # MPS memory optimizations
    pipe.enable_attention_slicing()
    pipe.enable_vae_slicing()

    console.print("[green]Pipeline loaded successfully.[/green]")
    return pipe


def generate_frames(
    pipe: AnimateDiffVideoToVideoPipeline,
    source_image: Image.Image,
    num_frames: int,
    strength: float,
    seed: int,
) -> list[Image.Image]:
    """Generate animation frames from a single source image."""
    # Duplicate image as a "video" input
    video_input = [source_image] * num_frames

    generator = torch.Generator(device="cpu").manual_seed(seed)

    output = pipe(
        video=video_input,
        prompt=PROMPT,
        negative_prompt=NEGATIVE_PROMPT,
        strength=strength,
        num_inference_steps=ANIMATE_NUM_STEPS,
        guidance_scale=ANIMATE_GUIDANCE_SCALE,
        generator=generator,
    )

    return output.frames[0]


def save_gif(
    frames: list[Image.Image],
    output_path: str,
    fps: int,
) -> int:
    """Save frames as a ping-pong looping GIF. Returns file size in bytes."""
    duration = int(1000 / fps)

    # Ping-pong: forward + reverse (minus endpoints to avoid stutter)
    pingpong = list(frames) + list(reversed(frames[1:-1]))

    pingpong[0].save(
        output_path,
        save_all=True,
        append_images=pingpong[1:],
        duration=duration,
        loop=0,
        optimize=True,
        disposal=2,
    )

    file_size = os.path.getsize(output_path)
    return file_size


def optimize_gif(gif_path: str) -> int | None:
    """Try to optimize GIF with gifsicle if available. Returns new size or None."""
    if not shutil.which("gifsicle"):
        console.print("[dim]gifsicle not found, skipping optimization.[/dim]")
        return None

    optimized_path = str(gif_path) + ".opt"

    try:
        subprocess.run(
            [
                "gifsicle",
                "--optimize=3",
                "--colors=256",
                "-o",
                optimized_path,
                gif_path,
            ],
            check=True,
            capture_output=True,
        )

        optimized_size = os.path.getsize(optimized_path)
        original_size = os.path.getsize(gif_path)

        if optimized_size < original_size:
            os.replace(optimized_path, gif_path)
            return optimized_size
        else:
            os.remove(optimized_path)
            return original_size
    except (subprocess.CalledProcessError, FileNotFoundError):
        if os.path.exists(optimized_path):
            os.remove(optimized_path)
        return None


def lossy_compress_gif(gif_path: str, lossy: int = 20) -> int | None:
    """Apply lossy compression with gifsicle. Returns new size or None."""
    if not shutil.which("gifsicle"):
        return None

    optimized_path = str(gif_path) + ".opt"

    try:
        subprocess.run(
            [
                "gifsicle",
                "--optimize=3",
                "--colors=256",
                f"--lossy={lossy}",
                "-o",
                optimized_path,
                gif_path,
            ],
            check=True,
            capture_output=True,
        )

        os.replace(optimized_path, gif_path)
        return os.path.getsize(gif_path)
    except (subprocess.CalledProcessError, FileNotFoundError):
        if os.path.exists(optimized_path):
            os.remove(optimized_path)
        return None


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable string."""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    return f"{size_bytes / 1024:.1f}KB"


def main():
    parser = argparse.ArgumentParser(
        description="Generate animated GIF of Sakura using AnimateDiff"
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Regenerate even if GIF already exists",
    )
    parser.add_argument(
        "--seed",
        "-s",
        type=int,
        default=ANIMATE_SEED,
        help=f"Random seed (default: {ANIMATE_SEED})",
    )
    parser.add_argument(
        "--strength",
        type=float,
        default=ANIMATE_STRENGTH,
        help=f"Animation strength 0.0-1.0 (default: {ANIMATE_STRENGTH})",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=ANIMATE_NUM_FRAMES,
        help=f"Number of frames to generate (default: {ANIMATE_NUM_FRAMES})",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=ANIMATE_FPS,
        help=f"GIF frame rate (default: {ANIMATE_FPS})",
    )
    parser.add_argument(
        "--image",
        type=str,
        default=str(ANIMATE_SOURCE),
        help=f"Source image path (default: {ANIMATE_SOURCE})",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=str(ANIMATE_OUTPUT),
        help=f"Output GIF path (default: {ANIMATE_OUTPUT})",
    )
    args = parser.parse_args()

    # Check if output already exists
    if os.path.exists(args.output) and not args.force:
        console.print(f"[green]Animated GIF already exists: {args.output}[/green]")
        console.print("Use --force to regenerate.")
        return

    # Validate source image
    if not os.path.exists(args.image):
        console.print(f"[red]Source image not found: {args.image}[/red]")
        return

    console.print("[bold magenta]Sakura Animation Generator[/bold magenta]")
    console.print(f"Source: {args.image}")
    console.print(f"Output: {args.output}")
    console.print(
        f"Settings: {args.frames} frames, {ANIMATE_WIDTH}x{ANIMATE_HEIGHT}, "
        f"strength={args.strength}, seed={args.seed}"
    )
    console.print()

    # Determine device
    device = IMAGE_DEVICE if torch.backends.mps.is_available() else "cpu"
    console.print(f"[dim]Using device: {device}[/dim]")

    # Load source image
    console.print("[dim]Loading source image...[/dim]")
    source = load_image(args.image).resize(
        (ANIMATE_WIDTH, ANIMATE_HEIGHT), Image.LANCZOS
    )

    # Load pipeline
    pipe = load_pipeline(device)

    # Generate frames
    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Generating animation frames...", total=None)
        frames = generate_frames(
            pipe,
            source,
            num_frames=args.frames,
            strength=args.strength,
            seed=args.seed,
        )
        progress.update(task, completed=True)

    console.print(f"[green]Generated {len(frames)} frames.[/green]")

    # Free GPU memory
    del pipe
    torch.mps.empty_cache() if device == "mps" else None

    # Save GIF
    console.print("[dim]Saving GIF...[/dim]")
    pingpong_count = len(frames) + max(0, len(frames) - 2)
    file_size = save_gif(frames, args.output, fps=args.fps)
    console.print(
        f"[dim]Raw GIF: {format_size(file_size)} "
        f"({pingpong_count} frames, {args.fps} FPS)[/dim]"
    )

    # Optimize if possible
    optimized_size = optimize_gif(args.output)
    if optimized_size is not None and optimized_size != file_size:
        console.print(
            f"[dim]Optimized: {format_size(file_size)} → "
            f"{format_size(optimized_size)}[/dim]"
        )
        file_size = optimized_size

    # Check against GitHub limit
    if file_size > MAX_GIF_SIZE:
        console.print(
            f"[yellow]GIF is {format_size(file_size)} "
            f"(over 10MB limit). Applying lossy compression...[/yellow]"
        )
        lossy_size = lossy_compress_gif(args.output, lossy=20)
        if lossy_size is not None:
            file_size = lossy_size
            console.print(f"[dim]After lossy compression: {format_size(file_size)}[/dim]")

        if file_size > MAX_GIF_SIZE:
            console.print(
                "[red]Warning: GIF still exceeds 10MB. "
                "Try --frames 20 or --strength 0.25[/red]"
            )

    console.print()
    console.print("[bold green]Animation complete![/bold green]")
    console.print(f"Output: {args.output}")
    console.print(f"Size: {format_size(file_size)}")
    console.print(f"Frames: {pingpong_count} (ping-pong loop)")
    console.print(f"Duration: {pingpong_count / args.fps:.1f}s @ {args.fps} FPS")


if __name__ == "__main__":
    main()
