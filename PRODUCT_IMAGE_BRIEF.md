# Product image brief — 24 products

The shop renders `product.image` when a product has one and falls back to a monogram tile
when it does not, so images can be added one at a time without breaking anything. The
database now carries `image` and `image_alt`; both are empty until a real render exists.

**Do not fill in a path before the file exists.** A path pointing at a missing file shows a
broken image on every card. (The front end now falls back to the monogram if a photo 404s,
but that is a safety net, not a plan.)

## Why this brief exists

Twenty-four images generated one at a time will look like twenty-four unrelated products.
What makes a catalogue read as a *range* is that every shot shares the same camera, the same
light, the same ground and the same crop. Fix those first, vary only the product.

## Fixed across every shot

- **Camera** — three-quarter front view, lens at product height, very slight downward tilt.
  Not top-down, not a flat lay. Garments on an invisible mannequin so they hold their shape.
- **Light** — one large soft key from upper left, soft fill from the right, no hard shadow.
  A soft contact shadow directly beneath the product to sit it on the surface.
- **Ground** — seamless pale blue-grey sweep, roughly `#eef4fa`, the site's own ground colour.
  No props, no pool, no towels bunched in the background, no text in the image.
- **Framing** — product centred, occupying about 80% of the frame height, even margins.
- **Output** — square, 1600x1600, JPEG, sRGB. Save to `assets/products/<sku-lowercase>.jpg`.
- **Branding** — the HV Swim mark applied where it would really sit on that garment, at a
  realistic size. Resist making the logo bigger than it would be in production; oversized
  branding is the clearest tell of a generated mock-up.

## Colourway

Navy `#06214a` base with aqua `#1d6fb0` detailing, gold `#ffd44d` used sparingly as a trim
accent only. Every garment in the range shares that palette so a kit photographs as a set.

## Per-product notes

Only the product-specific part is listed. Everything under "Fixed across every shot" applies
to all of them.

### Swimwear
- `HV-SWIMWEAR` — one-piece training swimsuit, chlorine-resistant matte fabric, mark on left chest.
- `HV-RASHIE` — long-sleeve child's rash top, flat-lock seams, mark centred on chest.
- `HV-SWIM-SHORTS` — child's board shorts, drawcord waist, small mark on left leg.

### Towels
- `HV-TOWEL` — folded rectangular towel, terry texture visible, embroidered mark on the top fold.
- `HV-HOODED-TOWEL` — child's hooded towel poncho, shown hanging so the hood reads clearly.
- `HV-MINI-HOODED-TOWEL` — the same in toddler size, visibly smaller proportions.

### Bottles and drinkware
- `HV-BOTTLE` — insulated stainless bottle, matte navy, screw lid, mark wrapped on the body.
- `HV-INSULATED-TUMBLER` — insulated coffee cup with sip lid, adult size.
- `HV-JUNIOR-WARM-CUP` — smaller child's warm-drink cup with a secure lid.

### Equipment
- `HV-GOGGLES` — swim goggles, smoke lens, navy strap, three-quarter view showing both lenses.
- `HV-TRAINING-MITTS` — pair of silicone training mitts, one flat and one angled.
- `HV-BAG` — mesh-panelled wet-gear pool bag, shown standing with the panel visible.

### Caps and headwear
- `HV-CAP` — silicone swim cap, domed as if worn, mark on the side.
- `HV-KIDS-SUN-HAT` — child's wide-brim sun hat with chin strap.
- `HV-INSTRUCTOR-CAP` — structured six-panel cap, embroidered mark on the front panel.

### Staff uniform
- `HV-STAFF-POLO` — short-sleeve polo, three-button placket, mark on left chest.
- `HV-STAFF-TEE` — technical short-sleeve shirt, slightly athletic cut.
- `HV-STAFF-SHORTS` — deck shorts with side pocket.
- `HV-STAFF-PUFFER-VEST` — quilted vest, full zip.
- `HV-STAFF-PUFFER-JACKET` — quilted jacket, full zip, matching the vest exactly.
- `HV-STAFF-TRACKPANTS` — tapered track pants, elastic cuff.
- `HV-TEAM-HOODIE` — pullover hoodie with front pouch.

### Family lifestyle
- `HV-FAMILY-TEE` — relaxed-fit cotton tee.
- `HV-FAMILY-CREW` — heavyweight crew sweatshirt, matching the tee's mark placement.

## Alt text

Write `image_alt` as a plain description of the product for someone who cannot see it —
"Navy long-sleeve child's rash top with the HV Swim mark on the chest" — not "product photo"
and not a repeat of the title.

## Once the images exist

1. Save them to `assets/products/` using the SKU in lowercase.
2. Set `image` and `image_alt` on each product row.
3. Run `node scripts/check-site.mjs`.
4. Do **not** add them to the service-worker precache. They are large and load on demand.

## Standing caveat

These are concept renders, not photographs of approved samples. `MERCH_PRODUCTION_PLAN.md`
requires approved sample photography or supplier-authorised mock-ups before anything is
published for sale. Keep the "concept" labelling on the shop until that happens.
