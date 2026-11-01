"""Keep browser scripts inside the production image and served by Flask."""
import re
import unittest
from pathlib import Path
import app as server

class DeploymentAssets(unittest.TestCase):
    def test_local_browser_scripts_included_in_image(self):
        html=Path('index.html').read_text()
        copies=' '.join(line for line in Path('Dockerfile').read_text().splitlines() if line.startswith('COPY '))
        for path in re.findall(r'<script[^>]+src="(/[^\"]+\.js)"',html):
            name=path.lstrip('/')
            with self.subTest(script=name):
                self.assertTrue(Path(name).is_file())
                self.assertIn(name,copies.split())
                with server.app.test_client().get(path) as response:
                    self.assertEqual(response.status_code,200)
                    self.assertIn('javascript',response.content_type)
