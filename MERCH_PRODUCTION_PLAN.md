# HV Swim merchandise production plan

The website now contains a nine-product launch catalogue and a Management → Merchandise workspace. No product has been sent to a supplier and no real checkout is active. Those boundaries are intentional until HV Swim owns the connected accounts, approves pricing and signs off physical samples.

## Recommended production route

| Product | Primary route | Why |
|---|---|---|
| Team swimwear | Specialist swim supplier | Requires chlorine-resistant fabric, reliable fit and approved print placement |
| Logo towel | VistaPrint or specialist textile supplier | Compare embroidery/print finish, absorbency, minimum quantity and delivered price |
| Drink bottle | VistaPrint/manual supplier | Good fit for bulk promotional drinkware; verify food-contact compliance and lid quality |
| Goggles | Specialist swim supplier | Fit, seal, materials and safety matter more than generic branding |
| Pool-deck bag | Printify or specialist supplier | Test ventilation and wet-gear durability before choosing the automated route |
| Silicone swim cap | Specialist swim supplier | Requires swim-specific silicone printing and colour proofing |
| Staff performance polo | VistaPrint/manual uniform supplier | Embroidery and garment consistency suit a controlled staff uniform order |
| Team hoodie | Printify → Shopify | A good candidate for on-demand sizing and direct fulfilment after a sample is approved |
| Instructor cap | VistaPrint or Printify | Select after comparing embroidery finish, fit and outdoor durability |

## Store and fulfilment architecture

1. Shopify is the public product, variant, pricing, stock, checkout, payment and refund system.
2. Printify connects to Shopify for approved POD products. Use manual order approval at launch so no order reaches production unexpectedly.
3. VistaPrint and specialist suppliers remain controlled purchase-order workflows. Their stock can still be represented in Shopify.
4. The HV Swim admin panel shows integration readiness and supplier assignments. It does not expose secret tokens to the browser.
5. Xero remains the accounting platform. Final Shopify-to-Xero reconciliation should use an approved connector or accountant-defined process.

## Release gates for every product

1. Obtain a transparent 300 DPI logo and preferably an approved vector master (SVG, EPS or print-ready PDF).
2. Confirm exact garment/product specifications, placement, colours and safe print area.
3. Order a physical sample and record the supplier, SKU, landed cost and lead time.
4. Test wear, washing and—where relevant—chlorine exposure.
5. Approve retail price, GST, margin, sizing chart, returns rules and product copy.
6. Photograph the approved sample or use supplier-authorised mock-ups.
7. Publish to Shopify and run a full mobile test order, fulfilment test, refund and Xero reconciliation.

## Print asset note

The supplied logo is suitable for the website and concept artwork. Production suppliers will normally need a transparent, high-resolution or vector version. Do not remove a background or redraw the mark without checking the original brand master; colour and edge changes are visible on uniforms and swimwear.
