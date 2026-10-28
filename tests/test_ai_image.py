import unittest

from bot.ai_image import (
    generate_image_png,
    is_image_generation_request,
    render_svg_png,
    sanitize_svg,
)


class ImageIntentTests(unittest.TestCase):
    def test_detects_direct_image_requests(self):
        self.assertTrue(is_image_generation_request("Make an image of a fish"))
        self.assertTrue(is_image_generation_request("Draw a tiny blue fish"))
        self.assertTrue(is_image_generation_request("Create a logo for my server"))

    def test_does_not_intercept_explanations_or_regular_chat(self):
        self.assertFalse(is_image_generation_request("How do I create an image?"))
        self.assertFalse(is_image_generation_request("What is a fish?"))
        self.assertFalse(is_image_generation_request("I like fish pictures"))


class SvgImageTests(unittest.TestCase):
    def test_sanitizes_and_renders_an_image(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
            '<circle cx="50" cy="50" r="35" fill="#21a6c7"/>'
            "</svg>"
        )
        png = render_svg_png(sanitize_svg(svg))
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_rejects_active_and_external_svg_content(self):
        with self.assertRaises(ValueError):
            sanitize_svg(
                '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
            )
        with self.assertRaises(ValueError):
            sanitize_svg(
                '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.com/a.png"/></svg>'
            )

    def test_model_output_is_rasterized(self):
        class FakeCompletions:
            @staticmethod
            def create(**_kwargs):
                class Message:
                    content = (
                        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
                        '<ellipse cx="50" cy="50" rx="30" ry="20" fill="orange"/>'
                        "</svg>"
                    )

                class Choice:
                    message = Message()

                class Response:
                    choices = [Choice()]

                return Response()

        class FakeClient:
            class chat:
                completions = FakeCompletions()

        png = generate_image_png(FakeClient(), "test-model", "a small orange fish")
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))


if __name__ == "__main__":
    unittest.main()
