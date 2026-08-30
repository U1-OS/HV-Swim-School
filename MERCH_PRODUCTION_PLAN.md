# HV Swim premium merchandise production plan

The V5.6 collection contains 21 planned products and a Management → Merchandise control
workspace. It is premium-only: no product becomes sellable until its materials, decoration,
fit, landed cost and physical sample are approved. The public saved collection is a demand-
planning preview; no real checkout, stock reservation or supplier order is fabricated.

## Premium collection and primary route

| Product family | Products | Primary route | Mandatory approval |
|---|---|---|---|
| Kids aquatic apparel | Team swimwear, rashie, swim shorts | Specialist aquatic supplier | Chlorine resistance, seams, fit, movement and decoration durability |
| Towels | Embroidered pool towel, kids hooded towel | Premium textile / VistaPrint comparison | Absorbency, hood comfort, colourfastness and stitch-back comfort |
| Cold-drink gear | Named pool bottle | VistaPrint or approved bulk supplier | Food-contact evidence, lid, drop, wash and rub testing |
| Warm drinkware | Adult insulated coffee cup, junior warm-drink cup | Approved drinkware supplier | Food-contact evidence, insulation, lid and heat-cycle testing; junior cup must be spill-resistant and labelled parent-supervised, warm—not hot |
| Aquatic equipment | Goggles, silicone training mitts, silicone swim cap | Specialist aquatic supplier | Fit, materials, hygiene/returns, coach-directed use and chlorine durability; mitts are not a flotation or safety device |
| Bags and poolside hats | Ventilated swim bag, kids sun hat | Printify/VistaPrint/specialist comparison | Wet ventilation, zips, abrasion, fit, shade coverage and embroidery/transfer sample |
| Staff core uniform | Embroidered polo, performance shirt, quick-dry shorts | Approved uniform supplier; Printify only for eligible mapped shirt | Movement, opacity, pockets, repeatable sizing, wear/wash and stitched-logo sample |
| Staff warm uniform | Hoodie, puffer vest, puffer jacket, tracksuit pants | Printify/VistaPrint/authorised teamwear comparison | Embroidery/transfer quality, warmth, weather performance, movement, sizing, landed cost and Australian lead time |
| Staff headwear | Instructor cap | Printify/VistaPrint comparison | Embroidery, fit, sun coverage and outdoor durability |

## Premium brand and logo rule

Recognised blank or teamwear labels—including Nike, Puma, Gildan and comparable brands—may
be considered only when supplied through an authorised reseller/decorator with permission
for the proposed HV Swim decoration. Their names are sourcing possibilities, not current
partners, endorsements or licences. Never add a third-party logo to the website or a mock-up
without the supplier's current product and artwork rights.

HV Swim's full-colour mark is appropriate for digital concepts. Premium embroidery needs a
manually checked vector master, supplier digitisation and an approved stitched sample. Use
embroidered HV branding for towels, polos, jackets, vests, track pants and caps when the
material and backing remain comfortable; use a tested transfer/print only where embroidery
would harm stretch, comfort or water performance.

## Store and fulfilment architecture

1. Shopify is the customer-facing source of truth for approved products, variants, GST,
   stock, checkout, payment, refunds and order history.
2. Printify has an official Shopify connection, but this repository currently provides
   read-only catalogue readiness and mapping controls only. Production becomes live after
   the HV Swim accounts are connected, a physical sample passes and a complete test order
   succeeds.
3. VistaPrint is a manual design/quote/purchase-order route. No public VistaPrint Shopify or
   ordering API is claimed. Approved stock is entered into Shopify after it arrives.
4. Specialist swim and uniform suppliers remain controlled quote, proof and purchase-order
   workflows. Pool-specific products are never routed to generic POD merely because a
   superficially similar catalogue item exists.
5. Management records each Shopify GID, eligible Printify product ID or manual quote/sample/
   PO reference without exposing supplier costs or private mappings to the public API.
6. Xero remains the accounting platform. Final Shopify-to-Xero reconciliation requires an
   accountant-approved connector and chart/tax mapping.

## Release gates for every product

1. Confirm the premium specification, intended audience, supplier and authorised decoration
   rights.
2. Supply the approved vector/print artwork and record the supplier's safe print/stitch area.
3. Record the exact blank/product SKU, sizes, colours, minimum order, lead time, landed cost
   and Shopify/Printify/manual supplier reference.
4. Order a physical sample for each material/decoration family.
5. Test fit, comfort, washing, colour, hardware and—where applicable—chlorine, wet abrasion,
   food contact, heat, weather and child-safe use.
6. Approve GST-inclusive retail price, margin, size chart, care, personalisation, hygiene and
   Australian Consumer Law returns wording.
7. Photograph the approved sample or use supplier-authorised product imagery.
8. Publish only approved variants to Shopify; keep Printify manual order approval enabled for
   launch.
9. Run mobile/desktop checkout, shipping, fulfilment, cancellation, refund and accounting
   reconciliation tests before accepting customer orders.

## Supplier readiness references

- Printify Shopify connection: <https://help.printify.com/hc/en-us/articles/4483630095505-How-can-I-connect-my-Shopify-store>
- Printify API reference: <https://developers.printify.com/>
- VistaPrint AU promotional merchandise: <https://www.vistaprint.com.au/custom-promotional-merch>
- VistaPrint AU active/workwear: <https://www.vistaprint.com.au/clothing-bags/active-workwear>

These URLs show current supplier capabilities, not an HV Swim account connection or a
guarantee that a specific product is available from an Australian fulfiller. Recheck
availability, shipping and terms when each sample order is raised.
