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

  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const money = cents => new Intl.NumberFormat('en-AU',{style:'currency',currency:'AUD'}).format(Number(cents || 0) / 100);
  const slug = value => String(value || '').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
  const sizeList = product => {
    if (Array.isArray(product.sizes)) return product.sizes;
    try { return JSON.parse(product.sizes || '[]'); } catch (_) { return []; }
  };
  const normalise = (product,source) => {
    if (source === 'shopify') {
      const variants = product.variants?.edges?.map(edge => edge.node) || [];
      const first = variants[0];
      return {id:product.id,sku:slug(product.handle || product.title),title:product.title,category:'Shopify',description:product.description || 'Connected Shopify product.',price_cents:Math.round(Number(first?.price?.amount || 0)*100),sizes:variants.map(item=>item.title).filter(title=>title!=='Default Title'),status:first?.availableForSale?'available':'unavailable',image:product.featuredImage?.url,variant_id:first?.id,variants};
    }
    return product;
  };
  const visualClass = product => `product-${slug(product.sku || product.title)}`;
  const visual = product => product.image ? `<img src="${esc(product.image)}" alt="${esc(product.title)}">` : `<div class="shop-product-crop ${visualClass(product)}" role="img" aria-label="${esc(product.title)} concept"></div>`;
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
      return `<article class="shop-card reveal visible" style="--reveal-delay:${Math.min(index*55,220)}ms"><button class="shop-product-visual" type="button" data-product-view="${esc(product.id)}" aria-label="View ${esc(product.title)}">${visual(product)}<span class="shop-product-badge">${product.status==='available'?'Available':'Collection concept'}</span><span class="shop-quick-view">Quick view</span></button><div class="shop-card-copy"><div class="shop-card-heading"><span class="shop-category">${esc(product.category)}</span><span>${sizes.length?`${sizes.length} ${sizes.length===1?'option':'options'}`:'Sizing pending'}</span></div><h3>${esc(product.title)}</h3><p>${esc(product.description)}</p><div class="shop-sizes">${sizes.slice(0,4).map(size=>`<span>${esc(size)}</span>`).join('')||'<span>Final sizing pending</span>'}${sizes.length>4?`<span>+${sizes.length-4}</span>`:''}</div><div class="shop-card-foot"><div><strong>${money(product.price_cents)}</strong><small>Preview price</small></div><button type="button" class="shop-add-button" data-product-add="${esc(product.id)}">Add <span aria-hidden="true">+</span></button></div></div></article>`;
    }).join('') || '<div class="empty-state">No products match that search. Try another category or clear the search.</div>';
  }

  function addToCart(product,size,quantity=1) {
    const selectedSize = size || sizeList(product)[0] || 'Standard';
    const key = cartKey(product.id,selectedSize);
    const existing = cart.find(item=>item.key===key);
    if (existing) existing.quantity = Math.min(20,Number(existing.quantity)+Number(quantity));
    else cart.push({key,id:String(product.id),sku:product.sku,title:product.title,category:product.category,size:selectedSize,quantity:Number(quantity),price_cents:Number(product.price_cents||0),variant_id:product.variant_id||null});
    saveCart();
    openCart();
  }

  function renderCart() {
    const itemCount = cart.reduce((sum,item)=>sum+Number(item.quantity||0),0);
    const subtotal = cart.reduce((sum,item)=>sum+Number(item.quantity||0)*Number(item.price_cents||0),0);
    document.querySelectorAll('[data-cart-count]').forEach(element=>element.textContent=String(itemCount));
    document.getElementById('cart-subtotal').textContent=money(subtotal);
    const items=document.getElementById('cart-items');
    if (!cart.length) items.innerHTML='<div class="cart-empty"><span>◇</span><h3>Your preview cart is empty.</h3><p>Choose preferred products and variants to create a lesson-day collection list.</p><button class="btn btn-soft" type="button" data-cart-close>Explore the collection</button></div>';
    else items.innerHTML=cart.map(item=>`<article class="cart-item" data-cart-key="${esc(item.key)}"><div class="cart-item-thumb"><span>${esc((item.title||'H').charAt(0))}</span></div><div class="cart-item-copy"><span>${esc(item.category)}</span><strong>${esc(item.title)}</strong><small>${esc(item.size)} · ${money(item.price_cents)} each</small><div class="cart-item-controls"><button type="button" data-cart-change="-1" aria-label="Decrease ${esc(item.title)} quantity">−</button><b>${item.quantity}</b><button type="button" data-cart-change="1" aria-label="Increase ${esc(item.title)} quantity">+</button><button type="button" data-cart-remove>Remove</button></div></div><strong>${money(Number(item.price_cents)*Number(item.quantity))}</strong></article>`).join('');
    const action=document.getElementById('cart-primary-action');
    const summary=cart.map(item=>`${item.quantity}× ${item.title} (${item.size})`).join(', ');
    action.textContent=catalogueSource==='shopify'?'Sign in to continue checkout':'Send collection interest';
    action.href=catalogueSource==='shopify'?'login.html':`enquire.html?${new URLSearchParams({merch:summary||'HV Swim Collection interest'})}`;
    action.classList.toggle('disabled',!cart.length);
    action.setAttribute('aria-disabled',String(!cart.length));
  }

  function openCart() {
    document.getElementById('cart-drawer').classList.add('open');
    document.getElementById('cart-drawer').setAttribute('aria-hidden','false');
    document.querySelector('.cart-backdrop').hidden=false;
    document.body.classList.add('no-scroll');
  }
  function closeCart() {
    document.getElementById('cart-drawer').classList.remove('open');
    document.getElementById('cart-drawer').setAttribute('aria-hidden','true');
    document.querySelector('.cart-backdrop').hidden=true;
    document.body.classList.remove('no-scroll');
  }

  function openProduct(id) {
    const product=products.find(item=>String(item.id)===String(id));
    if (!product) return;
    const sizes=sizeList(product);
    const dialog=document.getElementById('product-dialog');
    document.getElementById('product-dialog-content').innerHTML=`<div class="dialog-product-visual">${visual(product)}<span class="dialog-concept-label">HV Swim Collection 01</span></div><div class="dialog-product-copy"><span class="shop-category">${esc(product.category)}</span><h2>${esc(product.title)}</h2><strong class="dialog-price">${money(product.price_cents)}</strong><p>${esc(product.description)}</p><div class="product-option"><label for="dialog-size">Preferred option</label><select id="dialog-size">${(sizes.length?sizes:['Standard']).map(size=>`<option>${esc(size)}</option>`).join('')}</select></div><div class="product-option"><label for="dialog-quantity">Quantity</label><select id="dialog-quantity">${[1,2,3,4,5].map(value=>`<option value="${value}">${value}</option>`).join('')}</select></div><div class="data-boundary"><strong>${product.status==='available'?'Connected product':'Collection concept'}:</strong> ${product.status==='available'?'Availability comes from the connected Shopify catalogue; sign-in is required before checkout.':'Add this preferred option to the demo cart. No stock is reserved and no payment is taken until supplier samples and Shopify are approved.'}</div><button class="btn btn-primary" type="button" data-dialog-add="${esc(product.id)}">Add to preview cart</button></div>`;
    dialog.showModal();
  }

  document.querySelectorAll('[data-shop-filter]').forEach(button=>button.addEventListener('click',()=>{
    activeFilter=button.dataset.shopFilter;
    document.querySelectorAll('[data-shop-filter]').forEach(item=>item.classList.toggle('active',item===button));
    render();
  }));
  document.getElementById('shop-search')?.addEventListener('input',event=>{searchTerm=event.target.value.trim().toLowerCase();render();});
  grid.addEventListener('click',event=>{
    const view=event.target.closest('[data-product-view]');
    const add=event.target.closest('[data-product-add]');
    if (view) openProduct(view.dataset.productView);
    if (add) { const product=products.find(item=>String(item.id)===String(add.dataset.productAdd)); if(product)addToCart(product); }
  });
  document.getElementById('product-dialog-content')?.addEventListener('click',event=>{
    const button=event.target.closest('[data-dialog-add]'); if(!button)return;
    const product=products.find(item=>String(item.id)===String(button.dataset.dialogAdd));
    if(product){addToCart(product,document.getElementById('dialog-size').value,document.getElementById('dialog-quantity').value);document.getElementById('product-dialog').close();}
  });
  document.querySelector('.dialog-close')?.addEventListener('click',()=>document.getElementById('product-dialog').close());
  document.getElementById('product-dialog')?.addEventListener('click',event=>{if(event.target===event.currentTarget)event.currentTarget.close();});
  document.addEventListener('click',event=>{
    if(event.target.closest('[data-cart-open]'))openCart();
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
  document.getElementById('cart-primary-action')?.addEventListener('click',event=>{if(!cart.length)event.preventDefault();});
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&document.getElementById('cart-drawer').classList.contains('open'))closeCart();});

  renderCart();
  fetch('/api/products',{headers:{Accept:'application/json'}}).then(async response=>{
    const payload=await response.json(); if(!response.ok)throw new Error(payload.detail||'Catalogue unavailable');
    catalogueSource=payload.source;
    products=(payload.products||[]).map(product=>normalise(product,payload.source));
    const live=payload.source==='shopify';
    document.getElementById('shop-source').innerHTML=`<span class="status ${live?'open':'changed'}">${live?'Live Shopify catalogue':'Nine-product preview'}</span>`;
    document.getElementById('cart-mode-status').className=`status ${live?'open':'changed'}`;
    document.getElementById('cart-mode-status').textContent=live?'Shopify catalogue connected':'Collection preview';
    document.getElementById('cart-mode-copy').textContent=live?'Connected products are visible. Sign in before secure checkout.':'Your choices save on this device. No stock is reserved and no payment is taken.';
    render(); renderCart();
  }).catch(()=>{
    grid.innerHTML='<div class="empty-state">The catalogue is temporarily unavailable. Please enquire with the HV Swim team.</div>';
    document.getElementById('shop-result-count').textContent='Catalogue temporarily unavailable';
    document.getElementById('shop-source').innerHTML='<span class="status closed">Catalogue unavailable</span>';
  });
})();
