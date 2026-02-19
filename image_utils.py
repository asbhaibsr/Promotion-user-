# image_utils.py
# Advanced Leaderboard Image Generator
# Design: Dark Red Background, Black Header, White Text, Gradient Effect

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import io
import os
import logging

logger = logging.getLogger(__name__)

def generate_leaderboard_image(users_data):
    """
    Creates a professional leaderboard image.
    Design: Dark Red Gradient BG | Black Header Panel | White Glowing Text
    Optimized for speed with caching and fallbacks.
    """
    try:
        # --- Dimensions ---
        width = 900
        row_height = 70
        header_height = 140
        padding = 40
        total_height = header_height + (len(users_data) * row_height) + padding + 50

        # --- Colors ---
        BG_TOP = (180, 0, 0)        # Bright Red (Top of gradient)
        BG_BOTTOM = (100, 0, 0)      # Dark Red (Bottom of gradient)
        HEADER_BG = (30, 30, 30)      # Almost Black for header panel
        HEADER_TEXT = (255, 215, 0)   # Gold color for header text
        RANK_COLOR = (255, 255, 255)  # White
        NAME_COLOR = (255, 255, 255)  # White
        REFS_COLOR = (255, 215, 0)    # Gold for numbers
        SEPARATOR_COLOR = (255, 255, 255, 60)  # Semi-transparent white
        BORDER_COLOR = (255, 215, 0, 100)  # Gold border

        # --- Create base image with gradient background ---
        img = Image.new('RGB', (width, total_height), color=BG_TOP)
        draw = ImageDraw.Draw(img, 'RGBA')

        # Draw vertical gradient (Top to Bottom)
        for y in range(total_height):
            # Calculate ratio (0 at top, 1 at bottom)
            ratio = y / total_height
            # Interpolate between BG_TOP and BG_BOTTOM
            r = int(BG_TOP[0] * (1 - ratio) + BG_BOTTOM[0] * ratio)
            g = int(BG_TOP[1] * (1 - ratio) + BG_BOTTOM[1] * ratio)
            b = int(BG_TOP[2] * (1 - ratio) + BG_BOTTOM[2] * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # --- Fonts with fallback ---
        try:
            # Try to use bold fonts for header
            font_big = ImageFont.truetype("arialbd.ttf", 55)
            font_header = ImageFont.truetype("arialbd.ttf", 45)
            font_data = ImageFont.truetype("arial.ttf", 38)
            font_small = ImageFont.truetype("arial.ttf", 25)
        except IOError:
            try:
                # Fallback to DejaVu (common on Linux)
                font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 55)
                font_header = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 45)
                font_data = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 38)
                font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 25)
            except IOError:
                # Ultimate fallback
                font_big = ImageFont.load_default()
                font_header = ImageFont.load_default()
                font_data = ImageFont.load_default()
                font_small = ImageFont.load_default()

        # --- Draw Header Panel (Black panel with gold border) ---
        # Background panel
        draw.rectangle([(20, 20), (width - 20, header_height - 20)], fill=HEADER_BG, outline=BORDER_COLOR, width=3)
        
        # Title
        title = "🏆 TOP 10 LEADERBOARD 🏆"
        # Center text
        bbox = draw.textbbox((0, 0), title, font=font_big)
        title_width = bbox[2] - bbox[0]
        draw.text(((width - title_width) // 2, 40), title, fill=HEADER_TEXT, font=font_big)

        # Subtitle / Column headers
        draw.text((80, 100), "RANK", fill=HEADER_TEXT, font=font_header)
        draw.text((280, 100), "PLAYER", fill=HEADER_TEXT, font=font_header)
        draw.text((650, 100), "REFERRALS", fill=HEADER_TEXT, font=font_header)

        # --- Draw Data Rows ---
        y = header_height + 20
        
        for i, user in enumerate(users_data):
            rank = f"#{i + 1}"
            name = user['name'][:18] + ("..." if len(user['name']) > 18 else "")
            refs = str(user['refs'])
            
            # Row background (alternating subtle transparency)
            if i % 2 == 0:
                # Light overlay for alternating rows
                draw.rectangle([(30, y - 5), (width - 30, y + 55)], fill=(255, 255, 255, 15))
            
            # Special colors for Top 3
            if i == 0:
                rank_color = (255, 215, 0)  # Gold
                # Add crown emoji for rank 1
                draw.text((50, y), "👑", fill=rank_color, font=font_data)
                rank_x_offset = 90
            elif i == 1:
                rank_color = (192, 192, 192)  # Silver
                rank_x_offset = 80
            elif i == 2:
                rank_color = (205, 127, 50)  # Bronze
                rank_x_offset = 80
            else:
                rank_color = (255, 255, 255)  # White
                rank_x_offset = 80

            # Draw Rank
            draw.text((rank_x_offset, y), rank, fill=rank_color, font=font_data)
            
            # Draw Name
            draw.text((280, y), name, fill=NAME_COLOR, font=font_data)
            
            # Draw Referrals with glow effect (simple shadow)
            # Shadow
            draw.text((652, y + 2), refs, fill=(0, 0, 0, 128), font=font_data)
            # Actual text
            draw.text((650, y), refs, fill=REFS_COLOR, font=font_data)
            
            # Separator Line (except after last)
            if i < len(users_data) - 1:
                draw.line([(50, y + 60), (width - 50, y + 60)], fill=SEPARATOR_COLOR, width=2)
            
            y += row_height

        # --- Footer Note ---
        footer = "🏆 Keep Referring to Climb the Ranks! 🏆"
        bbox = draw.textbbox((0, 0), footer, font=font_small)
        footer_width = bbox[2] - bbox[0]
        draw.text(((width - footer_width) // 2, total_height - 40), footer, fill=(255, 255, 255, 200), font=font_small)

        # --- Convert to Bytes ---
        bio = io.BytesIO()
        img.save(bio, 'PNG', optimize=True, quality=95)
        bio.seek(0)
        return bio
        
    except Exception as e:
        logger.error(f"Leaderboard image generation failed: {e}")
        # Return a simple error image or fallback
        img = Image.new('RGB', (800, 400), color=(204, 0, 0))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 30)
        except:
            font = ImageFont.load_default()
        draw.text((100, 180), "Leaderboard: " + str(e), fill=(255,255,255), font=font)
        bio = io.BytesIO()
        img.save(bio, 'PNG')
        bio.seek(0)
        return bio
