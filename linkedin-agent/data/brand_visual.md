# Purands AI — Visual Identity

This file is read at runtime by the Visual Designer agent. It defines the look of
every generated visual (images and charts) so they resemble Purands brand posts.
Edit it freely; no code change is needed.

## Palette (use these exact colours)
- Primary purple / accent: #7C5CFC (vivid violet). This is the signature colour,
  used for highlights, key numbers, primary shapes, and the main illustration
  subject.
- Light purple / lilac: #B9A5F7 (secondary accent, soft highlights, second data
  series).
- Glow purple: #C9A9FF (soft neon-purple glow for emphasis text or accents).
- Deep base (dark cards): #1E1836 (near-black indigo used for dark panels with
  white text).
- Lavender background (light): a soft gradient from #EEE9F9 to #F4F1FB.
- Ink on light backgrounds: #2A2340. Ink on dark backgrounds: #FFFFFF.

## Style
- Clean, modern, professional. Flat-vector / soft isometric business
  illustration, the kind used in polished B2B SaaS marketing.
- Generous whitespace, rounded corners, subtle geometric accents (small dots,
  sparkles, thin connector lines) in purple tints.
- Friendly flat-vector people and objects rendered in the purple palette above
  (purple hair/clothing, lilac props), on a light lavender background.
- Soft, tasteful. No harsh gradients, no drop-shadow clutter, no stock-photo
  realism, no 3D render look.

## Rules for generated images
- ALWAYS build the palette above into the image prompt explicitly (name the
  purple hex tones and the lavender background) so the output is on-brand.
- No text or words rendered inside the image (image models garble text). Convey
  the idea visually; the caption carries the words.
- No logos, no wordmarks, no real people's faces, no brand names spelled out.
- No charts drawn as an image (real charts are rendered separately as SVG).

## Rules for charts
- Charts already render in the Purands palette (purple bars/lines on the dark
  panel). Keep titles/labels short and factual.
