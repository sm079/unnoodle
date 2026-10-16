"""The model files each real pipeline loads (app.catalogues.real), and where they come from.

A pod downloads them in this order, so the quickest and most used pipeline can run while the big video model is still
on its way. Each source is either a Hugging Face repo, whose paths mirror the renderer's models/ folder, or an https://
base that the files are fetched from as they are.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    repo: str
    # The folder under models/ to put the files in; empty when the repo already mirrors models/
    into: str
    files: tuple[str, ...]

    @property
    def spec(self) -> str:
        """As remote/models.sh takes it"""
        return f"{self.repo}::{self.into}::{','.join(self.files)}"


KLEIN_SPLIT = "https://huggingface.co/Comfy-Org/vae-text-encorder-for-flux-klein-9b/resolve/main/split_files"

FILES: dict[str, tuple[Source, ...]] = {
    # About 25 GB
    "krea2-turbo": (
        Source(
            "Comfy-Org/Krea-2",
            "",
            (
                "diffusion_models/krea2_turbo_fp8_scaled.safetensors",
                "text_encoders/qwen3vl_4b_fp8_scaled.safetensors",
                "vae/qwen_image_vae.safetensors",
            ),
        ),
    ),
    # About 18 GB; the weights are gated, so this needs a Hugging Face token whose account accepted the licence
    "flux2-klein-edit": (
        Source("black-forest-labs/FLUX.2-klein-9b-fp8", "diffusion_models", ("flux-2-klein-9b-fp8.safetensors",)),
        Source(f"{KLEIN_SPLIT}/text_encoders", "text_encoders", ("qwen_3_8b_fp8mixed.safetensors",)),
        Source(f"{KLEIN_SPLIT}/vae", "vae", ("flux2-vae.safetensors",)),
    ),
    # About 40 GB
    "minimax-h3": (
        Source(
            "Comfy-Org/MiniMax-H3",
            "",
            (
                "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors",
                "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
                "vae/minimax_h3_video_vae_fp16.safetensors",
                "vae/minimax_h3_audio_vae_fp32.safetensors",
            ),
        ),
        Source(
            "drbaph/MiniMax-H3-Turbo-Lora-ComfyUI",
            "loras",
            ("minimax_h3_turbo_v4_step600_ema_pruned_comfyui.safetensors",),
        ),
    ),
}
