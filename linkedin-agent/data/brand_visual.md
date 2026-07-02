# Purands AI — Visual Identity

This file is read at runtime by the Visual Designer agent. It defines the look of
every generated visual (images and charts) so they resemble Purands brand posts.
Edit it freely; no code change is needed.

## Palette — white-dominant, violet as an accent (clean, easy on the eyes)
White and soft off-white are the DOMINANT colours. Violet is an accent used
sparingly, not a full-bleed fill. Keep it light and airy; avoid large saturated
violet areas.
- Background (dominant): #FFFFFF white, or a very soft off-white #FAF9FE. Large
  areas should be white/near-white with generous whitespace.
- Primary violet (accent only): #7C5CFC. Use for a few key shapes, an accent
  object, thin lines, and small highlights - not as a big background block.
- Soft violet (secondary): #A98FF3, and pale lilac #D9CFF7 for gentle fills and
  tints.
- Ink / text tone: #2A2340 (deep indigo-grey) for any dark elements.
- Muted grey-violet: #6E6885 for secondary detail.
Avoid dark near-black indigo panels and heavy, high-saturation violet blocks -
they read as too bright/harsh. Favour white space with light violet accents.

## Style
- Clean, modern, professional, MINIMAL. Flat-vector / soft isometric business
  illustration, the kind used in polished B2B SaaS marketing.
- Lots of white space. Rounded corners, subtle geometric accents (small dots,
  sparkles, thin connector lines) in light violet tints.
- Friendly flat-vector people and objects with light violet accents (a violet
  prop or highlight, soft lilac shading) on a predominantly white background -
  NOT fully purple characters on a purple field.
- Soft, tasteful, uncluttered. No harsh gradients, no neon, no drop-shadow
  clutter, no stock-photo realism, no 3D render look.

## Rules for generated images
- ALWAYS build the palette above into the image prompt explicitly: a WHITE /
  soft off-white background with VIOLET (#7C5CFC) accents, light and airy, plenty
  of whitespace. Violet is an accent, not the whole image.
- No text or words rendered inside the image (image models garble text). Convey
  the idea visually; the caption carries the words.
- No logos, no wordmarks, no real people's faces, no brand names spelled out.
- No charts drawn as an image (real charts are rendered separately as SVG).

## Rules for charts
- Charts already render in the Purands palette (purple bars/lines on the dark
  panel). Keep titles/labels short and factual.
