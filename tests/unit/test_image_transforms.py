"""
Unit tests for on-demand image transform logic.
Tests parse_thumb_spec() and generate_thumb_on_demand() from ImageProcessor.
"""
import io
import pytest
from PIL import Image

from app.services.image_processor import ImageProcessor


# ─── parse_thumb_spec ─────────────────────────────────────────────────────────

class TestParseThumbSpec:

    def test_basic_crop(self):
        w, h, mode = ImageProcessor.parse_thumb_spec("300x200")
        assert w == 300 and h == 200 and mode == "crop"

    def test_fit_modifier(self):
        w, h, mode = ImageProcessor.parse_thumb_spec("300x200f")
        assert mode == "fit"

    def test_top_modifier(self):
        w, h, mode = ImageProcessor.parse_thumb_spec("300x200t")
        assert mode == "top"

    def test_bottom_modifier(self):
        w, h, mode = ImageProcessor.parse_thumb_spec("300x200b")
        assert mode == "bottom"

    def test_proportional_width(self):
        w, h, mode = ImageProcessor.parse_thumb_spec("300x0")
        assert w == 300 and h == 0 and mode == "crop"

    def test_proportional_height(self):
        w, h, mode = ImageProcessor.parse_thumb_spec("0x200")
        assert w == 0 and h == 200 and mode == "crop"

    def test_case_insensitive(self):
        w, h, mode = ImageProcessor.parse_thumb_spec("300X200F")
        assert mode == "fit"

    def test_whitespace_stripped(self):
        w, h, mode = ImageProcessor.parse_thumb_spec("  100x100  ")
        assert w == 100 and h == 100

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            ImageProcessor.parse_thumb_spec("300")

    def test_invalid_zero_both_raises(self):
        with pytest.raises(ValueError):
            ImageProcessor.parse_thumb_spec("0x0")

    def test_invalid_letters_raises(self):
        with pytest.raises(ValueError):
            ImageProcessor.parse_thumb_spec("WxH")


# ─── generate_thumb_on_demand ─────────────────────────────────────────────────

def _make_test_image(width=600, height=400, color=(200, 100, 50)) -> bytes:
    """Create a solid-color JPEG image for testing."""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


class TestGenerateThumbOnDemand:

    @pytest.mark.asyncio
    async def test_center_crop_exact_dimensions(self):
        src = _make_test_image(600, 400)
        result = await ImageProcessor.generate_thumb_on_demand(src, 300, 200, mode="crop")
        with Image.open(io.BytesIO(result)) as img:
            assert img.size == (300, 200)

    @pytest.mark.asyncio
    async def test_fit_mode_pads_to_exact_dimensions(self):
        src = _make_test_image(600, 400)
        result = await ImageProcessor.generate_thumb_on_demand(src, 300, 200, mode="fit")
        with Image.open(io.BytesIO(result)) as img:
            assert img.size == (300, 200)

    @pytest.mark.asyncio
    async def test_top_crop_mode(self):
        src = _make_test_image(600, 400)
        result = await ImageProcessor.generate_thumb_on_demand(src, 300, 200, mode="top")
        with Image.open(io.BytesIO(result)) as img:
            assert img.width == 300
            assert img.height == 200

    @pytest.mark.asyncio
    async def test_bottom_crop_mode(self):
        src = _make_test_image(600, 400)
        result = await ImageProcessor.generate_thumb_on_demand(src, 300, 200, mode="bottom")
        with Image.open(io.BytesIO(result)) as img:
            assert img.width == 300
            assert img.height == 200

    @pytest.mark.asyncio
    async def test_proportional_resize_by_width(self):
        """Wx0 → resize to width W, auto-calculate height from aspect ratio."""
        src = _make_test_image(600, 400)  # 3:2 aspect
        result = await ImageProcessor.generate_thumb_on_demand(src, 300, 0, mode="crop")
        with Image.open(io.BytesIO(result)) as img:
            assert img.width == 300
            # Height should be proportional: 300 * (400/600) = 200
            assert img.height == 200

    @pytest.mark.asyncio
    async def test_proportional_resize_by_height(self):
        """0xH → resize to height H, auto-calculate width from aspect ratio."""
        src = _make_test_image(600, 400)  # 3:2 aspect
        result = await ImageProcessor.generate_thumb_on_demand(src, 0, 200, mode="crop")
        with Image.open(io.BytesIO(result)) as img:
            assert img.height == 200
            # Width should be proportional: 200 * (600/400) = 300
            assert img.width == 300

    @pytest.mark.asyncio
    async def test_output_is_jpeg(self):
        src = _make_test_image(200, 200)
        result = await ImageProcessor.generate_thumb_on_demand(src, 100, 100)
        with Image.open(io.BytesIO(result)) as img:
            assert img.format == "JPEG"

    @pytest.mark.asyncio
    async def test_rgba_source_converted_to_rgb(self):
        """RGBA source should be composited onto white before JPEG output."""
        img = Image.new("RGBA", (200, 200), (255, 0, 0, 128))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        src = buf.getvalue()

        result = await ImageProcessor.generate_thumb_on_demand(src, 100, 100)
        with Image.open(io.BytesIO(result)) as out:
            assert out.mode == "RGB"

    @pytest.mark.asyncio
    async def test_invalid_image_raises_value_error(self):
        with pytest.raises(ValueError):
            await ImageProcessor.generate_thumb_on_demand(b"not-an-image", 100, 100)
