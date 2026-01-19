# app/agents/tools/image_fetch.py
"""
Image fetching tool for logos and headers.
Reusable across agency, vendor, and other agents.
"""

import os
import re
import hashlib
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO

from . import Tool, ToolContext, ToolResult, register_tool


class ImageFetchTool(Tool):
    """
    Fetches and saves logos and header images.
    
    Supports:
    - Scraping from website (favicon, meta tags, common paths)
    - Saving to appropriate static directories
    """
    
    # Common logo locations to check
    LOGO_PATHS = [
        '/favicon.ico',
        '/favicon.png',
        '/logo.png',
        '/logo.svg',
        '/images/logo.png',
        '/assets/logo.png',
        '/img/logo.png',
    ]
    
    # Minimum dimensions for valid logos
    MIN_LOGO_SIZE = 32
    MIN_HEADER_WIDTH = 400
    
    @property
    def name(self) -> str:
        return 'image_fetch'
    
    def execute(self, context: ToolContext) -> ToolResult:
        """
        Fetch an image for an entity.
        
        Expected params:
        - entity_type: "agency" | "vendor"
        - entity_name: str
        - short_name: str (for filename)
        - website_url: str | None
        - image_type: "logo" | "header"
        """
        params = context.params
        entity_type = params.get('entity_type', 'agency')
        entity_name = params.get('entity_name', '')
        short_name = params.get('short_name', '')
        website_url = params.get('website_url')
        image_type = params.get('image_type', 'logo')
        
        logs = [f"Starting {image_type} fetch for {entity_name}"]
        
        if not short_name:
            # Generate short_name from entity_name
            short_name = self._generate_short_name(entity_name)
            logs.append(f"Generated short_name: {short_name}")
        
        # Determine target directory
        if entity_type == 'agency':
            if image_type == 'logo':
                target_dir = 'app/static/images/transit_logos'
            else:
                target_dir = 'app/static/images/transit_headers'
        else:  # vendor
            if image_type == 'logo':
                target_dir = 'app/static/images/vendor_logos'
            else:
                target_dir = 'app/static/images/vendor_headers'
        
        # Ensure directory exists
        os.makedirs(target_dir, exist_ok=True)
        
        # Try to fetch image
        image_data = None
        source = None
        confidence = 0.0
        
        if website_url:
            logs.append(f"Attempting to fetch from website: {website_url}")
            
            if image_type == 'logo':
                image_data, source = self._fetch_logo_from_website(website_url, logs)
            else:
                image_data, source = self._fetch_header_from_website(website_url, logs)
            
            if image_data:
                confidence = 0.85
        
        if not image_data:
            logs.append("Could not fetch image from website")
            return ToolResult(
                success=False,
                data={'reason': 'Image not found'},
                confidence=0.0,
                logs=logs,
            )
        
        # Save the image
        filename = f"{short_name}_{image_type}.png"
        filepath = os.path.join(target_dir, filename)
        
        try:
            # Convert to PNG and save
            img = Image.open(BytesIO(image_data))
            
            # Convert to RGBA if necessary
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Resize if needed
            if image_type == 'logo':
                # Standardize logo size
                img.thumbnail((256, 256), Image.Resampling.LANCZOS)
            else:
                # Headers should be wider
                if img.width < self.MIN_HEADER_WIDTH:
                    logs.append(f"Header too narrow ({img.width}px), may need manual replacement")
                    confidence *= 0.7
            
            img.save(filepath, 'PNG')
            logs.append(f"Saved image to {filepath}")
            
            return ToolResult(
                success=True,
                data={
                    'filepath': filepath,
                    'filename': filename,
                    'source': source,
                    'dimensions': f"{img.width}x{img.height}",
                },
                confidence=confidence,
                logs=logs,
            )
            
        except Exception as e:
            logs.append(f"Error processing image: {str(e)}")
            return ToolResult(
                success=False,
                data={'error': str(e)},
                confidence=0.0,
                logs=logs,
                error=str(e),
            )
    
    def _generate_short_name(self, name: str) -> str:
        """Generate a filesystem-safe short name."""
        # Remove common suffixes
        name = re.sub(r'\s+(transit|authority|agency|district|metro)$', '', name, flags=re.I)
        # Convert to lowercase, replace spaces with underscores
        name = name.lower().strip()
        name = re.sub(r'[^a-z0-9]+', '_', name)
        name = name.strip('_')
        return name or 'unknown'
    
    def _fetch_logo_from_website(self, url: str, logs: list) -> tuple[bytes | None, str | None]:
        """Attempt to fetch a logo from a website."""
        try:
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            
            # First, try to find logo in page HTML
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                # Get the homepage
                logs.append("Fetching homepage to search for logo...")
                response = client.get(url)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Check meta tags
                    og_image = soup.find('meta', property='og:image')
                    if og_image and og_image.get('content'):
                        img_url = urljoin(base_url, og_image['content'])
                        logs.append(f"Found og:image: {img_url}")
                        img_data = self._download_image(client, img_url)
                        if img_data:
                            return img_data, 'og:image'
                    
                    # Check for logo in img tags
                    for img in soup.find_all('img'):
                        src = img.get('src', '')
                        alt = img.get('alt', '').lower()
                        cls = ' '.join(img.get('class', [])).lower()
                        
                        if 'logo' in src.lower() or 'logo' in alt or 'logo' in cls:
                            img_url = urljoin(base_url, src)
                            logs.append(f"Found logo img: {img_url}")
                            img_data = self._download_image(client, img_url)
                            if img_data:
                                return img_data, 'html_img'
                    
                    # Check link tags for favicon
                    for link in soup.find_all('link', rel=lambda x: x and 'icon' in x):
                        href = link.get('href')
                        if href:
                            img_url = urljoin(base_url, href)
                            logs.append(f"Found favicon link: {img_url}")
                            img_data = self._download_image(client, img_url)
                            if img_data and len(img_data) > 1000:  # Skip tiny favicons
                                return img_data, 'favicon_link'
                
                # Try common paths
                for path in self.LOGO_PATHS:
                    img_url = urljoin(base_url, path)
                    logs.append(f"Trying common path: {path}")
                    img_data = self._download_image(client, img_url)
                    if img_data:
                        return img_data, f'common_path:{path}'
            
        except Exception as e:
            logs.append(f"Error fetching from website: {str(e)}")
        
        return None, None
    
    def _fetch_header_from_website(self, url: str, logs: list) -> tuple[bytes | None, str | None]:
        """Attempt to fetch a header/banner image from a website."""
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.get(url)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Check og:image (often used for social sharing banners)
                    og_image = soup.find('meta', property='og:image')
                    if og_image and og_image.get('content'):
                        img_url = urljoin(url, og_image['content'])
                        logs.append(f"Found og:image for header: {img_url}")
                        img_data = self._download_image(client, img_url)
                        if img_data:
                            return img_data, 'og:image'
                    
                    # Look for header/banner images
                    for img in soup.find_all('img'):
                        src = img.get('src', '')
                        cls = ' '.join(img.get('class', [])).lower()
                        parent_cls = ' '.join(img.parent.get('class', [])).lower() if img.parent else ''
                        
                        if any(kw in (src.lower() + cls + parent_cls) for kw in ['header', 'banner', 'hero']):
                            img_url = urljoin(url, src)
                            logs.append(f"Found header/banner img: {img_url}")
                            img_data = self._download_image(client, img_url)
                            if img_data:
                                return img_data, 'header_img'
        
        except Exception as e:
            logs.append(f"Error fetching header: {str(e)}")
        
        return None, None
    
    def _download_image(self, client: httpx.Client, url: str) -> bytes | None:
        """Download an image and return raw bytes."""
        try:
            response = client.get(url)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                if 'image' in content_type or url.endswith(('.png', '.jpg', '.jpeg', '.ico', '.svg', '.gif')):
                    return response.content
        except Exception:
            pass
        return None


# Register the tool
register_tool(ImageFetchTool())