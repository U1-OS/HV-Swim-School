(() => {
  'use strict';
  const grid = document.getElementById('shop-grid');
  if (!grid) return;

  const CART_KEY = 'hv-swim-v48-preview-cart';
  let products = [];
  let activeFilter = 'all';
  let searchTerm = '';
  let catalogueSource = 'planned_catalogue';
  let cart = loadCart();
  let cartOpener = null;
  let productOpener = null;

  const PRODUCT_DETAILS = {
    'HV-SWIMWEAR': {material:'Chlorine-resistant performance fabric — final blend pending sample',care:'Cool fresh-water rinse after every swim; shade dry',personalisation:'HV Swim identity only; optional name placement under review'},
    'HV-TOWEL': {material:'Soft, absorbent pool towel — weight and embroidery pending sample',care:'Cold machine wash; avoid fabric softener for best absorbency',personalisation:'Embroidered HV Swim mark; individual name option under review'},
    'HV-BOTTLE': {material:'Insulated or BPA-free bottle specification to be confirmed',care:'Hand wash lid and seals; bottle care follows final supplier specification',personalisation:'Name field planned after dishwasher and rub testing'},
    'HV-GOGGLES': {material:'Soft-seal training goggles from an approved swim supplier',care:'Rinse after use; air dry away from direct sun; do not rub lenses',personalisation:'No custom print planned; HV Swim packaging option under review'},
    'HV-BAG': {material:'Ventilated, quick-dry wet-gear construction',care:'Empty after lessons; wipe clean and air dry fully',personalisation:'Name panel and HV Swim mark planned'},
    'HV-CAP': {material:'Specialist silicone swim cap',care:'Rinse, pat dry and store flat away from sharp items',personalisation:'Durable team print pending stretch and chlorine testing'},
    'HV-STAFF-POLO': {material:'Breathable performance knit with embroidered identity',care:'Cold gentle wash; wash inside-out; shade dry',personalisation:'Role or staff name embroidery can be added after uniform approval'},
    'HV-TEAM-HOODIE': {material:'Mid-weight brushed fleece — final composition pending POD sample',care:'Cold wash inside-out; shade dry; do not iron decoration',personalisation:'HV Swim decoration included; individual names optional'},
    'HV-INSTRUCTOR-CAP': {material:'Lightweight adjustable performance cap',care:'Hand wash and reshape while damp',personalisation:'Embroidered HV Swim identity; instructor label under review'}
  };
  const KITS = {
    'first-splash': ['HV-GOGGLES','HV-CAP','HV-TOWEL','HV-BOTTLE'],
    'lesson-day': ['HV-SWIMWEAR','HV-GOGGLES','HV-TOWEL','HV-BAG','HV-BOTTLE'],
    'pool-deck': ['HV-STAFF-POLO','HV-TEAM-HOODIE','HV-INSTRUCTOR-CAP','HV-BOTTLE']
  };

  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const money = cents => new Intl.NumberFormat('en-AU',{style:'currency',currency:'AUD'}).format(Number(cents || 0) / 100);
  const slug = value => String(value || '').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
  const request = window.HVSwim?.fetchJSON || (async url => {
    const response = await fetch(url, {headers:{Accept:'application/json'}});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || 'Request unavailable');
    return payload;
  });
  const categoryFor = product => {
    const value = `${product.productType || ''} ${product.title || ''}`.toLowerCase();
    if (/swimwear|swimsuit|rash/.test(value)) return 'Swimwear';
    if (/uniform|polo|hoodie|staff/.test(value)) return 'Uniforms';
    if (/towel/.test(value)) return 'Towels';
    if (/bottle|drink/.test(value)) return 'Bottles';
    if (/bag/.test(value)) return 'Bags';
    if (/cap|hat/.test(value)) return 'Caps';
    if (/goggle|equipment/.test(value)) return 'Equipment';
    return product.productType || 'Other';
  };
  const sizeList = product => {
    if (Array.isArray(product.sizes)) return product.sizes;
    try { return JSON.parse(product.sizes || '[]'); } catch (_) { return []; }
  };
  const normalise = (product,source) => {
    if (source === 'shopify') {
      const variants = (product.variants?.edges || []).map(edge => edge.node).filter(Boolean).map(variant => ({
        id:String(variant.id),
        title:variant.title || 'Standard',
        availableForSale:Boolean(variant.availableForSale),
        price_cents:Math.round(Number(variant.price?.amount || 0) * 100)
      }));
      const priceVariant = variants.find(variant => variant.availableForSale) || variants[0];
      return {id:product.id,sku:slug(product.handle || product.title),title:product.title,category:categoryFor(product),description:product.description || 'Connected Shopify product.',price_cents:Number(priceVariant?.price_cents || 0),sizes:variants.map(item=>item.title === 'Default Title' ? 'Standard' : item.title),status:variants.some(variant=>variant.availableForSale)?'available':'unavailable',image:product.featuredImage?.url,variants};
    }
    return product;
  };
  const visualClass = product => `product-${slug(product.sku || product.title)} ${['Uniforms'].includes(product.category)?'uniform-studio-crop':''}`;
  const visual = product => product.image ? `<img src="${esc(product.image)}" alt="${esc(product.title)}" loading="lazy" decoding="async">` : `<div class="shop-product-crop ${visualClass(product)}" role="img" aria-label="${esc(product.title)} concept"></div>`;
  const cartKey = (id,size) => `${id}::${size || 'Standard'}`;

  function loadCart() {
    try {
      const saved = JSON.parse(localStorage.getItem(CART_KEY));
      return Array.isArray(saved) ? saved.filter(item=>item && item.id && Number(item.quantity)>0) : [];
    } catch (_) { return []; }
  }
  function saveCart() {
    try { localStorage.setItem(CART_KEY,JSON.stringify(cart)); } catch (_) {}
    renderCart();
  }
  function visibleProducts() {
    return products.filter(product => {
      const categoryMatch = activeFilter === 'all' || product.category === activeFilter || (activeFilter === 'Caps' && ['Caps','Equipment'].includes(product.category));
      const searchMatch = !searchTerm || `${product.title} ${product.description} ${product.category}`.toLowerCase().includes(searchTerm);
      return categoryMatch && searchMatch;
    });
  }
  function render() {
    const visible = visibleProducts();
    document.getElementById('shop-result-count').textContent = `${visible.length} ${visible.length === 1 ? 'product' : 'products'} showing`;
    grid.innerHTML = visible.map((product,index) => {
      const sizes = sizeList(product);
      const chooseVariant = catalogueSource === 'shopify';
      const available = product.status === 'available';
      const badge = available ? 'Available' : (chooseVariant ? 'Currently unavailable' : 'Collection concept');
      const addLabel = chooseVariant ? (available ? 'Choose option' : 'Unavailable') : 'Add';
      return `<article class="shop-card reveal visible" style="--reveal-delay:${Math.min(index*55,220)}ms"><button class="shop-product-visual" type="button" data-product-view="${esc(product.id)}" aria-label="View ${esc(product.title)}">${visual(product)}<span class="shop-product-badge">${badge}</span><span class="shop-quick-view">Quick view</span></button><div class="shop-card-copy"><div class="shop-card-heading"><span class="shop-category">${esc(product.category)}</span><span>${sizes.length?`${sizes.length} ${sizes.length===1?'option':'options'}`:'Sizing pending'}</span></div><h3>${esc(product.title)}</h3><p>${esc(product.description)}</p><div class="shop-sizes">${sizes.slice(0,4).map(size=>`<span>${esc(size)}</span>`).join('')||'<span>Final sizing pending</span>'}${sizes.length>4?`<span>+${sizes.length-4}</span>`:''}</div><div class="shop-card-foot"><div><strong>${money(product.price_cents)}</strong><small>${chooseVariant?'Current price':'Indicative price'}</small></div><button type="button" class="shop-add-button" data-product-add="${esc(product.id)}" ${chooseVariant&&!available?'disabled':''}>${addLabel} <span aria-hidden="true">${chooseVariant?'→':'+'}</span></button></div></div></article>`;
    }).join('') || '<div class="empty-state"><strong>Nothing matches that search.</strong><p>Try a different category, or clear the search to see the whole collection.</p><button type="button" class="btn btn-outline btn-small" data-clear-search>Show everything</button></div>';
  }

  function addToCart(product,selection,quantity=1,openDrawer=true) {
    let selectedSize = selection || sizeList(product)[0] || 'Standard';
    let variantId = null;
    let price = Number(product.price_cents || 0);
    if (catalogueSource === 'shopify') {
      const variant = product.variants?.find(item => String(item.id) === String(selection));
      if (!variant || !variant.availableForSale) return false;
      selectedSize = variant.title === 'Default Title' ? 'Standard' : variant.title;
      variantId = variant.id;
      price = Number(variant.price_cents || product.price_cents || 0);
    }
    const key = cartKey(product.id,variantId || selectedSize);
    const existing = cart.find(item=>item.key===key);
    if (existing) existing.quantity = Math.min(20,Number(existing.quantity)+Number(quantity));
    else cart.push({key,id:String(product.id),sku:product.sku,title:product.title,category:product.category,size:selectedSize,quantity:Number(quantity),price_cents:price,variant_id:variantId});
    saveCart();
    if (openDrawer) openCart();
    return true;
  }

  function addKit(kitId) {
    if (catalogueSource === 'shopify') {
      const status=document.getElementById('kit-builder-status');
      if(status){status.classList.remove('complete');status.innerHTML='<span>→</span><p><strong>Choose options from the live collection.</strong> Sizes and variants must be selected for each product before it can be added.</p>';}
      document.getElementById('collection')?.scrollIntoView({behavior:'smooth',block:'start'});
      return;
    }
    const kitProducts=(KITS[kitId]||[]).map(sku=>products.find(product=>product.sku===sku)).filter(Boolean);
    if (!kitProducts.length) return;
    kitProducts.forEach(product=>{
      const selectedSize=sizeList(product)[0]||'Standard';
      const key=cartKey(product.id,selectedSize);
      const existing=cart.find(item=>item.key===key);
      if(existing) existing.quantity=Math.min(20,Number(existing.quantity)+1);
      else cart.push({key,id:String(product.id),sku:product.sku,title:product.title,category:product.category,size:selectedSize,quantity:1,price_cents:Number(product.price_cents||0),variant_id:null});
    });
    saveCart();
    const status=document.getElementById('kit-builder-status');
    if(status){status.classList.add('complete');status.innerHTML=`<span>✓</span><p><strong>${kitProducts.length} products added.</strong> Review sizes and quantities in your saved collection before sending an enquiry.</p>`;}
    openCart();
  }

  function renderCart() {
    const itemCount = cart.reduce((sum,item)=>sum+Number(item.quantity||0),0);
    const subtotal = cart.reduce((sum,item)=>sum+Number(item.quantity||0)*Number(item.price_cents||0),0);
    document.querySelectorAll('[data-cart-count]').forEach(element=>element.textContent=String(itemCount));
    document.getElementById('cart-subtotal').textContent=money(subtotal);
    const items=document.getElementById('cart-items');
    if (!cart.length) items.innerHTML='<div class="cart-empty"><span>◇</span><h3>Your saved collection is empty.</h3><p>Choose preferred products and options to create a lesson-day collection list.</p><button class="btn btn-soft" type="button" data-cart-close>Explore the collection</button></div>';
    else items.innerHTML=cart.map(item=>`<article class="cart-item" data-cart-key="${esc(item.key)}"><div class="cart-item-thumb"><span>${esc((item.title||'H').charAt(0))}</span></div><div class="cart-item-copy"><span>${esc(item.category)}</span><strong>${esc(item.title)}</strong><small>${esc(item.size)} · ${money(item.price_cents)} each</small><div class="cart-item-controls"><button type="button" data-cart-change="-1" aria-label="Decrease ${esc(item.title)} quantity">−</button><b>${item.quantity}</b><button type="button" data-cart-change="1" aria-label="Increase ${esc(item.title)} quantity">+</button><button type="button" data-cart-remove>Remove</button></div></div><strong>${money(Number(item.price_cents)*Number(item.quantity))}</strong></article>`).join('');
    const action=document.getElementById('cart-primary-action');
    const summary=cart.map(item=>`${item.quantity}× ${item.title} (${item.size})`).join(', ');
    const needsReselection=catalogueSource==='shopify'&&cart.some(item=>!item.variant_id);
    action.textContent=catalogueSource==='shopify'?'Sign in to continue checkout':'Send collection interest';
    action.href=catalogueSource==='shopify'?'login.html':`enquire.html?${new URLSearchParams({merch:summary||'HV Swim Collection interest'})}`;
    action.classList.toggle('disabled',!cart.length||needsReselection);
    action.setAttribute('aria-disabled',String(!cart.length||needsReselection));
    if(needsReselection){
      document.getElementById('cart-mode-copy').textContent='Some saved preview items need to be reselected from the live Shopify catalogue before checkout.';
    }
  }

  const cartDrawer=document.getElementById('cart-drawer');
  const pageRegions=[document.querySelector('.site-header'),document.querySelector('.shop-launch-bar'),document.querySelector('main'),document.querySelector('.site-footer'),document.querySelector('.shop-mobile-bar')].filter(Boolean);
  const setPageInert=value=>pageRegions.forEach(region=>{region.inert=value;});
  function openCart(opener=document.activeElement) {
    if(cartDrawer.classList.contains('open'))return;
    cartOpener=opener instanceof HTMLElement?opener:null;
    cartDrawer.inert=false;
    cartDrawer.classList.add('open');
    cartDrawer.setAttribute('aria-hidden','false');
    document.querySelector('.cart-backdrop').hidden=false;
    setPageInert(true);
    document.body.classList.add('no-scroll');
    requestAnimationFrame(()=>cartDrawer.querySelector('[data-cart-close]')?.focus());
  }
  function closeCart() {
    if(!cartDrawer.classList.contains('open'))return;
    cartDrawer.classList.remove('open');
    cartDrawer.setAttribute('aria-hidden','true');
    cartDrawer.inert=true;
    document.querySelector('.cart-backdrop').hidden=true;
    setPageInert(false);
    document.body.classList.toggle('no-scroll',Boolean(document.querySelector('.nav-links.open')));
    const target=cartOpener;cartOpener=null;
    if(target?.isConnected)target.focus();
  }

  function openProduct(id,opener=document.activeElement) {
    const product=products.find(item=>String(item.id)===String(id));
    if (!product) return;
    const sizes=sizeList(product);
    const detail=PRODUCT_DETAILS[product.sku]||{material:'Final material specification pending supplier approval',care:'Care instructions published after physical sample approval',personalisation:'Personalisation options to be confirmed'};
    const dialog=document.getElementById('product-dialog');
    productOpener=opener instanceof HTMLElement?opener:null;
    const live=catalogueSource==='shopify';
    const available=!live||(product.variants||[]).some(variant=>variant.availableForSale);
    const options=live
      ? `<option value="">Choose an option</option>${(product.variants||[]).map(variant=>`<option value="${esc(variant.id)}" ${variant.availableForSale?'':'disabled'}>${esc(variant.title==='Default Title'?'Standard':variant.title)}${variant.availableForSale?'':' — unavailable'}</option>`).join('')}`
      : (sizes.length?sizes:['Standard']).map(size=>`<option value="${esc(size)}">${esc(size)}</option>`).join('');
    document.getElementById('product-dialog-content').innerHTML=`<div class="dialog-product-visual">${visual(product)}<span class="dialog-concept-label">HV Swim Collection</span></div><div class="dialog-product-copy"><span class="shop-category">${esc(product.category)}</span><h2 id="product-dialog-title">${esc(product.title)}</h2><strong class="dialog-price">${money(product.price_cents)}</strong><p>${esc(product.description)}</p><dl class="product-specs"><div><dt>Material direction</dt><dd>${esc(detail.material)}</dd></div><div><dt>Care</dt><dd>${esc(detail.care)}</dd></div><div><dt>Personalisation</dt><dd>${esc(detail.personalisation)}</dd></div></dl><div class="product-dialog-options"><div class="product-option"><label for="dialog-size">${live?'Select option':'Preferred option'}</label><select id="dialog-size" required>${options}</select></div><div class="product-option"><label for="dialog-quantity">Quantity</label><select id="dialog-quantity">${[1,2,3,4,5].map(value=>`<option value="${value}">${value}</option>`).join('')}</select></div></div><p class="wizard-error" id="dialog-option-error" role="alert" hidden>Please choose an available option.</p><div class="info-note"><strong>${live?'Live catalogue':'Collection availability'}:</strong> ${live?(available?'Availability and options come from Shopify. Sign in is required before secure checkout.':'This product is currently unavailable in Shopify. You can still review its details and check again later.'):'No stock is reserved and no payment is taken while final samples and suppliers are approved.'}</div><button class="btn btn-primary" type="button" data-dialog-add="${esc(product.id)}" ${available?'':'disabled'}>${live?(available?'Add selected option':'Currently unavailable'):'Add to collection list'}</button></div>`;
    dialog.showModal();
  }

  document.querySelectorAll('[data-shop-filter]').forEach(button=>button.addEventListener('click',()=>{
    activeFilter=button.dataset.shopFilter;
    document.querySelectorAll('[data-shop-filter]').forEach(item=>{
      const selected=item===button;
      item.classList.toggle('active',selected);
      item.setAttribute('aria-pressed',String(selected));
    });
    render();
  }));
  document.getElementById('kit-grid')?.addEventListener('click',event=>{const button=event.target.closest('[data-kit-add]');if(button)addKit(button.dataset.kitAdd);});
  document.getElementById('shop-search')?.addEventListener('input',event=>{searchTerm=event.target.value.trim().toLowerCase();render();});
  // "Show everything" in the empty state clears both the search and the category filter.
  grid.addEventListener('click',event=>{
    if(!event.target.closest('[data-clear-search]'))return;
    searchTerm='';activeFilter='all';
    const input=document.getElementById('shop-search');if(input)input.value='';
    document.querySelectorAll('[data-shop-filter]').forEach(item=>{
      const selected=item.dataset.shopFilter==='all';
      item.classList.toggle('active',selected);
      item.setAttribute('aria-pressed',String(selected));
    });
    render();
  });
  grid.addEventListener('click',event=>{
    const view=event.target.closest('[data-product-view]');
    const add=event.target.closest('[data-product-add]');
    if (view) openProduct(view.dataset.productView,view);
    if (add) {
      const product=products.find(item=>String(item.id)===String(add.dataset.productAdd));
      if(product){
        if(catalogueSource==='shopify')openProduct(product.id,add);
        else addToCart(product);
      }
    }
  });
  document.getElementById('product-dialog-content')?.addEventListener('click',event=>{
    const button=event.target.closest('[data-dialog-add]'); if(!button)return;
    const product=products.find(item=>String(item.id)===String(button.dataset.dialogAdd));
    if(!product)return;
    const select=document.getElementById('dialog-size');
    const added=addToCart(product,select.value,document.getElementById('dialog-quantity').value,false);
    if(!added){
      const error=document.getElementById('dialog-option-error');error.hidden=false;select.setAttribute('aria-invalid','true');select.focus();return;
    }
    const opener=productOpener;
    document.getElementById('product-dialog').close();
    openCart(opener);
  });
  document.getElementById('product-dialog-content')?.addEventListener('change',event=>{
    if(event.target.id!=='dialog-size')return;
    event.target.removeAttribute('aria-invalid');
    const error=document.getElementById('dialog-option-error');if(error)error.hidden=true;
    if(catalogueSource==='shopify'){
      const productId=document.querySelector('[data-dialog-add]')?.dataset.dialogAdd;
      const product=products.find(item=>String(item.id)===String(productId));
      const variant=product?.variants?.find(item=>String(item.id)===String(event.target.value));
      const price=document.querySelector('.dialog-price');if(price&&variant)price.textContent=money(variant.price_cents);
    }
  });
  document.querySelector('.dialog-close')?.addEventListener('click',()=>document.getElementById('product-dialog').close());
  document.getElementById('product-dialog')?.addEventListener('click',event=>{if(event.target===event.currentTarget)event.currentTarget.close();});
  document.addEventListener('click',event=>{
    const opener=event.target.closest('[data-cart-open]');
    if(opener)openCart(opener);
    if(event.target.closest('[data-cart-close]'))closeCart();
  });
  document.getElementById('cart-items')?.addEventListener('click',event=>{
    const row=event.target.closest('[data-cart-key]'); if(!row)return;
    const item=cart.find(entry=>entry.key===row.dataset.cartKey); if(!item)return;
    if(event.target.closest('[data-cart-remove]'))cart=cart.filter(entry=>entry.key!==item.key);
    const change=event.target.closest('[data-cart-change]');
    if(change){item.quantity+=Number(change.dataset.cartChange);if(item.quantity<1)cart=cart.filter(entry=>entry.key!==item.key);}
    saveCart();
  });
  document.getElementById('cart-clear')?.addEventListener('click',()=>{cart=[];saveCart();});
  document.getElementById('cart-primary-action')?.addEventListener('click',event=>{if(event.currentTarget.getAttribute('aria-disabled')==='true')event.preventDefault();});
  document.addEventListener('keydown',event=>{
    if(!cartDrawer.classList.contains('open'))return;
    if(event.key==='Escape'){event.preventDefault();closeCart();return;}
    if(event.key!=='Tab')return;
    const stops=[...cartDrawer.querySelectorAll('a[href],button:not([disabled]),select:not([disabled]),input:not([disabled]),[tabindex]:not([tabindex="-1"])')].filter(element=>element.offsetParent!==null);
    if(!stops.length)return;
    const first=stops[0];const last=stops[stops.length-1];
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
  });

  cartDrawer.inert=true;
  document.querySelectorAll('[data-shop-filter]').forEach(button=>button.setAttribute('aria-pressed',String(button.classList.contains('active'))));
  renderCart();
  grid.setAttribute('aria-busy','true');
  request('/api/products',{headers:{Accept:'application/json'}}).then(payload=>{
    catalogueSource=payload.source;
    products=(payload.products||[]).map(product=>normalise(product,payload.source));
    const live=payload.source==='shopify';
    document.getElementById('shop-source').innerHTML=`<span class="status ${live?'open':'changed'}">${live?'Live Shopify catalogue':'Nine-product collection plan'}</span>`;
    document.getElementById('cart-mode-status').className=`status ${live?'open':'changed'}`;
    document.getElementById('cart-mode-status').textContent=live?'Shopify catalogue connected':'Collection in development';
    document.getElementById('cart-mode-copy').textContent=live?'Connected products are visible. Sign in before secure checkout.':'Your choices save on this device. No stock is reserved and no payment is taken.';
    render(); renderCart();
  }).catch(()=>{
    grid.innerHTML='<div class="empty-state"><strong>The collection is not loading right now.</strong><p>This is a temporary problem on our side. The range is still there — get in touch and the team can talk you through it.</p><a class="btn btn-blue btn-small" href="enquire.html">Talk to the team <span aria-hidden="true">&rarr;</span></a></div>';
    document.getElementById('shop-result-count').textContent='Catalogue temporarily unavailable';
    document.getElementById('shop-source').innerHTML='<span class="status closed">Catalogue unavailable</span>';
  }).finally(()=>grid.setAttribute('aria-busy','false'));
})();
