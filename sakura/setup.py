"""One-time setup script to generate emotion images for Sakura."""

import argparse
import logging
import os
from pathlib import Path

import torch
from diffusers import StableDiffusionXLPipeline, StableDiffusionXLImg2ImgPipeline, EulerDiscreteScheduler
from huggingface_hub import snapshot_download
from PIL import Image
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from .config import (
    CACHE_DIR,
    EMOTIONS,
    CHARACTER_BASE_PROMPT,
    EMOTION_PROMPTS,
    IMAGE_MODEL,
    IMAGE_DEVICE,
    # NSFW settings
    NSFW_AVAILABLE,
    NSFW_CACHE_DIR,
    NSFW_IMAGE_MODEL,
    NSFW_CFG_SCALE,
    NSFW_NUM_STEPS,
    NSFW_IMAGE_SIZE,
    NSFW_EMOTION_PROMPTS,
    NSFW_CHARACTER_PROMPT,
    NSFW_NEGATIVE_PROMPT,
)

logger = logging.getLogger(__name__)
console = Console()

# Animagine XL 4.0 recommended settings
GUIDANCE_SCALE = 5
NUM_INFERENCE_STEPS = 28
IMG2IMG_STRENGTH = 0.75

# Quality tags for Animagine XL 4.0
QUALITY_TAGS = "masterpiece, high score, great score, absurdres"

# Negative prompt for Animagine XL 4.0
NEGATIVE_PROMPT = (
    "lowres, bad anatomy, bad hands, text, error, missing finger, extra digits, "
    "fewer digits, cropped, worst quality, low quality, low score, bad score, "
    "average score, signature, watermark, username, blurry"
)


def get_full_prompt(emotion: str) -> str:
    """Build full prompt with character base + quality tags + emotion."""
    emotion_addition = EMOTION_PROMPTS.get(emotion, "")
    return f"{CHARACTER_BASE_PROMPT}, {QUALITY_TAGS}, {emotion_addition}"


def get_nsfw_prompt(emotion: str) -> str:
    """Build NSFW prompt with character base + emotion (NoobAI format)."""
    emotion_addition = NSFW_EMOTION_PROMPTS.get(emotion, "")
    return f"{NSFW_CHARACTER_PROMPT}, {emotion_addition}"


def ensure_model_downloaded(model_id: str, is_nsfw: bool = False) -> None:
    """Check if model is cached, download if not."""
    cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
    model_folder = f"models--{model_id.replace('/', '--')}"

    if not os.path.exists(os.path.join(cache_dir, model_folder)):
        if is_nsfw:
            console.print("[bold yellow]NSFW Mode: Generating images[/bold yellow]")
            console.print("[dim]These images are for personal use only.[/dim]")
            console.print()
            console.print("[bold]Downloading NoobAI XL (~6-7GB)...[/bold]")
            console.print("[dim]This may take 15-30 minutes depending on your connection.[/dim]")
        else:
            console.print(f"[bold]Downloading {model_id}...[/bold]")
            console.print("[dim]This may take 10-20 minutes depending on your connection.[/dim]")

        snapshot_download(repo_id=model_id, repo_type="model")
        console.print("[green]Model downloaded successfully![/green]")
    else:
        console.print(f"[dim]Model {model_id} already cached.[/dim]")


def load_nsfw_pipeline() -> StableDiffusionXLPipeline:
    """Load NoobAI XL with v-prediction scheduler."""
    console.print(f"[dim]Loading {NSFW_IMAGE_MODEL}...[/dim]")

    pipe = StableDiffusionXLPipeline.from_pretrained(
        NSFW_IMAGE_MODEL,
        torch_dtype=torch.float32,
        use_safetensors=True,
    )

    # Override scheduler with v-prediction
    pipe.scheduler = EulerDiscreteScheduler.from_config(
        pipe.scheduler.config,
        prediction_type="v_prediction",
    )

    pipe.to(IMAGE_DEVICE)
    pipe.enable_attention_slicing()
    pipe.enable_vae_slicing()

    console.print("[green]Model loaded successfully.[/green]")
    return pipe


def check_image_size(image_path: Path, expected_width: int, expected_height: int | None = None) -> bool:
    """Check if existing image matches expected size."""
    if expected_height is None:
        expected_height = expected_width
    if not image_path.exists():
        return False
    try:
        with Image.open(image_path) as img:
            return img.size == (expected_width, expected_height)
    except Exception:
        return False


def load_pipeline() -> StableDiffusionXLPipeline:
    """Load the txt2img pipeline with MPS optimizations."""
    console.print(f"[dim]Loading {IMAGE_MODEL}...[/dim]")
    console.print("[dim]First run will download ~7GB model.[/dim]")

    # Use float32 on MPS to avoid NaN issues with float16
    pipe = StableDiffusionXLPipeline.from_pretrained(
        IMAGE_MODEL,
        torch_dtype=torch.float32,
        use_safetensors=True,
        add_watermarker=False,
    )
    pipe.to(IMAGE_DEVICE)

    # MPS optimizations
    pipe.enable_attention_slicing()
    pipe.enable_vae_slicing()

    console.print("[green]Model loaded successfully.[/green]")
    return pipe


def generate_base_image(
    pipe: StableDiffusionXLPipeline,
    width: int,
    height: int,
    seed: int,
    prompt: str,
    negative_prompt: str,
    cfg_scale: float,
    num_steps: int,
) -> Image.Image:
    """Generate the base neutral image with fixed seed."""
    # Generator must be on CPU for MPS compatibility
    generator = torch.Generator("cpu").manual_seed(seed)

    result = pipe(
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        guidance_scale=cfg_scale,
        num_inference_steps=num_steps,
        generator=generator,
    )
    return result.images[0]


def generate_emotion_image(
    pipe_img2img: StableDiffusionXLImg2ImgPipeline,
    base_image: Image.Image,
    seed: int,
    prompt: str,
    negative_prompt: str,
    cfg_scale: float,
    num_steps: int,
) -> Image.Image:
    """Generate emotion variation using img2img from base."""
    # Generator must be on CPU for MPS compatibility
    generator = torch.Generator("cpu").manual_seed(seed)

    result = pipe_img2img(
        prompt=prompt,
        negative_prompt=negative_prompt,
        image=base_image,
        strength=IMG2IMG_STRENGTH,
        guidance_scale=cfg_scale,
        num_inference_steps=num_steps,
        generator=generator,
    )
    return result.images[0]


def generate_with_retry(
    generate_fn,
    *args,
    max_retries: int = 2,
    **kwargs,
) -> Image.Image | None:
    """Attempt generation with retry on failure."""
    for attempt in range(max_retries):
        try:
            return generate_fn(*args, **kwargs)
        except Exception as e:
            if attempt < max_retries - 1:
                console.print(f"[yellow]Generation failed, retrying...[/yellow]")
                torch.mps.empty_cache()
            else:
                logger.error(f"Generation failed after {max_retries} attempts: {e}")
                console.print(f"[red]Error: {e}[/red]")
                return None
    return None


def main():
    """Generate all emotion images."""
    parser = argparse.ArgumentParser(
        description="Generate emotion images for Sakura"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Regenerate all images even if they exist",
    )
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=42,
        help="Seed for character design (default: 42)",
    )
    parser.add_argument(
        "--size",
        type=int,
        choices=[512, 768, 1024],
        default=768,
        help="Image size (default: 768)",
    )
    parser.add_argument(
        "--emotion", "-e",
        type=str,
        choices=EMOTIONS,
        nargs='+',
        help="Generate only specific emotion(s)",
    )
    parser.add_argument(
        "--nsfw",
        action="store_true",
        help="Generate NSFW emotion images (requires local nsfw_prompts.py config)",
    )
    args = parser.parse_args()

    # Check NSFW availability
    if args.nsfw and not NSFW_AVAILABLE:
        console.print("[bold red]Error: NSFW mode requires nsfw_prompts.py[/bold red]")
        console.print()
        console.print("To enable NSFW mode:")
        console.print("1. Copy sakura/nsfw_prompts.example.py to sakura/nsfw_prompts.py")
        console.print("2. Customize the prompts in nsfw_prompts.py")
        console.print("3. Run this command again")
        console.print()
        console.print("[dim]Note: nsfw_prompts.py is gitignored and stays local.[/dim]")
        return

    # Determine which emotions to generate
    target_emotions = args.emotion if args.emotion else EMOTIONS.copy()

    # Set mode-specific settings
    if args.nsfw:
        cache_dir = NSFW_CACHE_DIR
        image_width, image_height = NSFW_IMAGE_SIZE
        cfg_scale = NSFW_CFG_SCALE
        num_steps = NSFW_NUM_STEPS
        negative_prompt = NSFW_NEGATIVE_PROMPT
        mode_label = "NSFW"
    else:
        cache_dir = CACHE_DIR
        image_width = image_height = args.size
        cfg_scale = GUIDANCE_SCALE
        num_steps = NUM_INFERENCE_STEPS
        negative_prompt = NEGATIVE_PROMPT
        mode_label = "SFW"

    # Ensure cache directory exists
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Check if neutral base needs regeneration
    neutral_path = cache_dir / "neutral.png"
    need_new_neutral = (
        (args.force and "neutral" in target_emotions)
        or not neutral_path.exists()
        or not check_image_size(neutral_path, image_width, image_height)
    )

    # Determine which emotions need generation
    if args.force:
        emotions_to_generate = target_emotions
    else:
        emotions_to_generate = [
            e for e in target_emotions
            if (
                (e == "neutral" and need_new_neutral)
                or (
                    e != "neutral"
                    and (
                        not (cache_dir / f"{e}.png").exists()
                        or not check_image_size(cache_dir / f"{e}.png", image_width, image_height)
                    )
                )
            )
        ]

    if not emotions_to_generate:
        console.print(f"[green]All {mode_label} emotion images already exist at correct size.[/green]")
        console.print("Use --force to regenerate.")
        return

    console.print(f"[bold magenta]Sakura Image Setup ({mode_label})[/bold magenta]")
    console.print(f"Generating {len(emotions_to_generate)} emotion image(s)")
    console.print(f"Size: {image_width}x{image_height}, Seed: {args.seed}")
    console.print()

    # Ensure model is downloaded
    model_id = NSFW_IMAGE_MODEL if args.nsfw else IMAGE_MODEL
    ensure_model_downloaded(model_id, is_nsfw=args.nsfw)

    # Load txt2img pipeline
    if args.nsfw:
        pipe = load_nsfw_pipeline()
    else:
        pipe = load_pipeline()

    # Generate base (neutral) image if needed
    base_image: Image.Image | None = None

    if need_new_neutral:
        console.print("[dim]Generating base (neutral) image...[/dim]")
        neutral_prompt = get_nsfw_prompt("neutral") if args.nsfw else get_full_prompt("neutral")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("neutral", total=None)
            base_image = generate_with_retry(
                generate_base_image,
                pipe,
                image_width,
                image_height,
                args.seed,
                neutral_prompt,
                negative_prompt,
                cfg_scale,
                num_steps,
            )
            progress.update(task, completed=True)

        if base_image is None:
            console.print("[red]Failed to generate base image. Aborting.[/red]")
            return

        base_image.save(neutral_path)
        console.print(f"[green]Saved: {neutral_path}[/green]")
    else:
        console.print("[dim]Loading existing neutral image as base...[/dim]")
        base_image = Image.open(neutral_path).convert("RGB")

    # Remove neutral from remaining emotions list
    other_emotions = [e for e in emotions_to_generate if e != "neutral"]

    # If only generating neutral, we're done
    if not other_emotions:
        console.print()
        console.print("[bold green]Setup complete![/bold green]")
        return

    # Convert to img2img pipeline (reuses components, saves memory)
    console.print("[dim]Converting to img2img pipeline...[/dim]")
    pipe_img2img = StableDiffusionXLImg2ImgPipeline.from_pipe(pipe)

    # Clear txt2img pipe to free memory
    del pipe
    torch.mps.empty_cache()

    # Generate remaining emotions
    console.print()
    failed_emotions = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            "Generating emotions",
            total=len(other_emotions),
        )

        for emotion in other_emotions:
            progress.update(task, description=f"Generating: {emotion}")

            emotion_prompt = get_nsfw_prompt(emotion) if args.nsfw else get_full_prompt(emotion)
            image = generate_with_retry(
                generate_emotion_image,
                pipe_img2img,
                base_image,
                args.seed,
                emotion_prompt,
                negative_prompt,
                cfg_scale,
                num_steps,
            )

            if image is not None:
                image_path = cache_dir / f"{emotion}.png"
                image.save(image_path)
            else:
                failed_emotions.append(emotion)

            progress.advance(task)

    # Cleanup
    del pipe_img2img
    torch.mps.empty_cache()

    console.print()
    if failed_emotions:
        console.print(
            f"[yellow]Warning: Failed to generate: {', '.join(failed_emotions)}[/yellow]"
        )
    console.print(f"[bold green]{mode_label} setup complete![/bold green]")
    console.print(f"Images saved to: {cache_dir}")


if __name__ == "__main__":
    main()
