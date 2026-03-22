import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


class MediaProcessor:
    """Local image/video edits used by the modify steps."""

    def image_transform_in_place(
        self,
        image_path: Path,
        operation: str,
        params: dict | None = None,
    ) -> None:
        params = params or {}
        path = Path(image_path)
        backup = path.with_suffix(path.suffix + ".orig")
        if not backup.exists():
            backup.write_bytes(path.read_bytes())

        img = Image.open(path).convert("RGB")
        if operation == "flip_horizontal":
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        elif operation == "zoom":
            zoom_factor = float(params.get("zoom_factor", 1.1))
            zoom_factor = max(1.01, min(2.0, zoom_factor))
            w, h = img.size
            nw = int(w / zoom_factor)
            nh = int(h / zoom_factor)
            left = max(0, (w - nw) // 2)
            top = max(0, (h - nh) // 2)
            cropped = img.crop((left, top, left + nw, top + nh))
            img = cropped.resize((w, h), Image.Resampling.LANCZOS)
        elif operation == "filter":
            name = str(params.get("filter", "none")).lower()
            if name == "bw":
                img = img.convert("L").convert("RGB")
            elif name == "blur":
                radius = float(params.get("radius", 1.8))
                img = img.filter(ImageFilter.GaussianBlur(radius=radius))
            elif name == "contrast":
                factor = float(params.get("factor", 1.2))
                img = ImageEnhance.Contrast(img).enhance(max(0.1, min(3.0, factor)))
            elif name == "vivid":
                factor = float(params.get("factor", 1.4))
                img = ImageEnhance.Color(img).enhance(max(0.1, min(3.0, factor)))
            # "none" intentionally leaves image unchanged.
        else:
            raise ValueError(f"Unsupported image transform operation: {operation}")

        img.save(path)

    def image_revert(self, image_path: Path) -> bool:
        path = Path(image_path)
        backup = path.with_suffix(path.suffix + ".orig")
        if not backup.exists():
            return False
        path.write_bytes(backup.read_bytes())
        return True

    def video_cut_in_place(self, video_path: Path, start_sec: float, end_sec: float) -> None:
        from moviepy.editor import VideoFileClip

        path = Path(video_path)
        with VideoFileClip(str(path)) as clip:
            duration = float(clip.duration or 0.0)
            start = max(0.0, min(duration, float(start_sec)))
            end = max(start + 0.05, min(duration, float(end_sec)))
            out = clip.subclip(start, end)
            tmp = path.with_suffix(".tmp.mp4")
            out.write_videofile(
                str(tmp),
                codec="libx264",
                audio_codec="aac",
                logger=None,
            )
        tmp.replace(path)

    def video_shake_in_place(
        self,
        video_path: Path,
        intensity: float = 0.03,
        first_seconds: float = 1.0,
    ) -> None:
        """Apply handheld-like jitter for the first second."""
        from moviepy.editor import VideoFileClip

        path = Path(video_path)
        intensity = max(0.02, min(0.04, float(intensity)))
        first_seconds = max(0.2, min(2.0, float(first_seconds)))

        with VideoFileClip(str(path)) as clip:
            w, h = clip.size
            max_shift = max(1, int(min(w, h) * intensity))

            def jitter(get_frame, t):
                frame = get_frame(t)
                if t > first_seconds:
                    return frame
                dx = int(max_shift * math.sin(t * 26.0))
                dy = int(max_shift * math.sin(t * 33.0 + 0.7))
                result = np.zeros_like(frame)

                src_x1 = max(0, -dx)
                src_x2 = min(w, w - dx) if dx >= 0 else w
                dst_x1 = max(0, dx)
                dst_x2 = dst_x1 + (src_x2 - src_x1)

                src_y1 = max(0, -dy)
                src_y2 = min(h, h - dy) if dy >= 0 else h
                dst_y1 = max(0, dy)
                dst_y2 = dst_y1 + (src_y2 - src_y1)

                if src_x2 > src_x1 and src_y2 > src_y1:
                    result[dst_y1:dst_y2, dst_x1:dst_x2] = frame[src_y1:src_y2, src_x1:src_x2]
                return result

            shaken = clip.fl(jitter)
            tmp = path.with_suffix(".tmp.mp4")
            shaken.write_videofile(
                str(tmp),
                codec="libx264",
                audio_codec="aac",
                logger=None,
            )
        tmp.replace(path)

    def subtitles_stub(self, video_path: Path) -> dict:
        _ = Path(video_path)
        return {
            "implemented": False,
            "message": "Subtitle generation is not implemented yet.",
        }
