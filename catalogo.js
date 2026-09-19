const CART_KEY = "imperialCart";
const WHATSAPP_NUMBER = "558581942691";

function loadCart() {
  try {
    const savedCart = JSON.parse(localStorage.getItem(CART_KEY));
    if (Array.isArray(savedCart)) {
      return savedCart.map(item => ({
        ...item,
        quantity: Number(item.quantity) > 0 ? Number(item.quantity) : 1
      }));
    }
  } catch (error) {
    console.warn("Erro ao ler carrinho do localStorage:", error);
  }

  return [];
}

let products = null;
let productsLoadError = false;
let cart = loadCart();
let selectedCategory = "Todos";

const categoriesElement = document.getElementById("categories");
const productsGrid = document.getElementById("productsGrid");
const cartButton = document.getElementById("cartButton");
const heroCartButton = document.getElementById("heroCartButton");
const cartDrawer = document.getElementById("cartDrawer");
const closeCartButton = document.getElementById("closeCart");
const cartItems = document.getElementById("cartItems");
const cartTotal = document.getElementById("cartTotal");
const checkoutButton = document.getElementById("checkoutButton");
const cartCount = document.getElementById("cartCount");
const productModal = document.getElementById("productModal");
const modalProductImage = document.getElementById("modalProductImage");
const modalProductCategory = document.getElementById("modalProductCategory");
const modalProductName = document.getElementById("modalProductName");
const modalProductDescription = document.getElementById("modalProductDescription");
const modalProductPrice = document.getElementById("modalProductPrice");
const modalProductPresentation = document.getElementById("modalProductPresentation");
const modalAddToCart = document.getElementById("modalAddToCart");
let selectedProductId = null;

function escapeHTML(value) {
  return String(value || "").replace(/[&<>\"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  }[char]));
}

function getDefaultProductImage() {
  return "images/default-product.svg";
}

function parsePrice(value) {
  const normalized = String(value || "").replace(/[^0-9,.-]/g, "");
  const safeValue = normalized.replace(/\./g, "").replace(",", ".");
  const parsed = Number.parseFloat(safeValue);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatCurrency(value) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL"
  }).format(Number(value || 0));
}

function saveCart() {
  localStorage.setItem(CART_KEY, JSON.stringify(cart));
}

function openCart() {
  if (cartDrawer) {
    cartDrawer.classList.add("open");
  }
}

function closeCart() {
  if (cartDrawer) {
    cartDrawer.classList.remove("open");
  }
}

function getPresentation(product) {
  return product.presentation || product.quantity || product.package || "";
}

function openProductDetails(productId) {
  const product = products.find(item => item.id === productId);
  if (!product || !productModal) return;

  selectedProductId = product.id;
  modalProductImage.src = product.image || getDefaultProductImage();
  modalProductImage.alt = product.name;
  modalProductCategory.textContent = product.category || "";
  modalProductName.textContent = product.name;
  modalProductDescription.textContent = product.description || "Detalhes disponíveis para atendimento personalizado.";
  modalProductPrice.textContent = product.price ? formatCurrency(parsePrice(product.price)) : "Preço sob consulta";
  modalProductPresentation.textContent = getPresentation(product);
  productModal.hidden = false;
  document.body.classList.add("modal-open");
}

function closeProductDetails() {
  if (!productModal) return;
  productModal.hidden = true;
  document.body.classList.remove("modal-open");
  selectedProductId = null;
}

function updateCartCount() {
  if (!cartCount) return;
  const totalItems = cart.reduce((sum, item) => sum + Number(item.quantity || 0), 0);
  cartCount.textContent = String(totalItems);
}

function addToCart(productId) {
  const product = products.find(item => item.id === productId);
  if (!product) return;

  const existingItem = cart.find(item => item.id === productId);
  if (existingItem) {
    existingItem.quantity += 1;
  } else {
    cart.push({
      id: product.id,
      name: product.name,
      category: product.category,
      price: product.price || "Preço sob consulta",
      image: product.image || getDefaultProductImage(),
      quantity: 1
    });
  }

  saveCart();
  renderCart();
  updateCartCount();
  openCart();
}

function removeFromCart(productId) {
  cart = cart.filter(item => item.id !== productId);
  saveCart();
  renderCart();
  updateCartCount();
}

function changeQuantity(productId, delta) {
  cart = cart
    .map(item => {
      if (item.id !== productId) return item;
      const nextQuantity = Number(item.quantity || 0) + delta;
      return nextQuantity > 0 ? { ...item, quantity: nextQuantity } : null;
    })
    .filter(Boolean);

  saveCart();
  renderCart();
  updateCartCount();
}

function buildCheckoutMessage() {
  if (!cart.length) {
    return "Olá! Gostaria de fazer um pedido na Imperial Pack.";
  }

  const orderLines = cart.map(item => {
    const unitPrice = parsePrice(item.price);
    const subtotal = unitPrice * Number(item.quantity || 0);
    return `• ${item.name} — ${item.quantity} unidade${item.quantity > 1 ? "s" : ""} — ${formatCurrency(unitPrice)} (Subtotal: ${formatCurrency(subtotal)})`;
  });

  const total = cart.reduce((sum, item) => sum + parsePrice(item.price) * Number(item.quantity || 0), 0);

  return [
    "Olá! Gostaria de fazer um pedido na Imperial Pack.",
    "",
    "Pedido:",
    ...orderLines,
    "",
    `Total: ${formatCurrency(total)}`,
    "",
    "Aguardo confirmação. Obrigado!"
  ].join("\n");
}

function handleCheckout() {
  if (!cart.length) return;
  const message = encodeURIComponent(buildCheckoutMessage());
  window.open(`https://wa.me/${WHATSAPP_NUMBER}?text=${message}`, "_blank", "noopener,noreferrer");
}

function renderCart() {
  if (!cartItems) return;

  if (!cart.length) {
    cartItems.innerHTML = '<div class="cart-empty">Seu carrinho está vazio.</div>';
    if (cartTotal) cartTotal.textContent = formatCurrency(0);
    if (checkoutButton) checkoutButton.disabled = true;
    return;
  }

  const total = cart.reduce((sum, item) => sum + parsePrice(item.price) * Number(item.quantity || 0), 0);

  cartItems.innerHTML = cart.map(item => {
    const itemPrice = parsePrice(item.price);
    const subtotal = itemPrice * Number(item.quantity || 0);

    return `
      <div class="cart-item">
        <img
          src="${escapeHTML(item.image || getDefaultProductImage())}"
          alt="${escapeHTML(item.name)}"
          onerror="this.onerror=null;this.src='images/default-product.svg';"
        />

        <div class="cart-item-info">
          <strong>${escapeHTML(item.name)}</strong>
          <span>${formatCurrency(itemPrice)}</span>
          <div class="cart-item-controls">
            <button type="button" data-cart-decrease="${item.id}" aria-label="Diminuir quantidade">−</button>
            <span>${item.quantity}</span>
            <button type="button" data-cart-increase="${item.id}" aria-label="Aumentar quantidade">+</button>
          </div>
        </div>

        <div class="cart-item-actions">
          <strong>${formatCurrency(subtotal)}</strong>
          <button type="button" class="remove-item" data-cart-remove="${item.id}">Remover</button>
        </div>
      </div>
    `;
  }).join("");

  if (cartTotal) cartTotal.textContent = formatCurrency(total);
  if (checkoutButton) checkoutButton.disabled = false;
}

function renderCategories() {
  if (!categoriesElement) return;

  const categories = ["Todos", ...new Set((products || []).map(product => product.category).filter(Boolean))];
  categoriesElement.innerHTML = categories.map(category => `
    <button
      class="category-button ${selectedCategory === category ? "active" : ""}"
      type="button"
      data-category="${category}"
    >
      ${category}
    </button>
  `).join("");
}

function selectCategory(category) {
  selectedCategory = category;
  render();
}

function renderProducts() {
  if (!productsGrid) return;

  if (productsLoadError) {
    productsGrid.innerHTML = `
      <div class="empty-state error-state">
        Não foi possível carregar o catálogo agora. Tente novamente mais tarde.
      </div>
    `;
    return;
  }

  if (!Array.isArray(products)) {
    productsGrid.innerHTML = '<div class="empty-state">Carregando produtos...</div>';
    return;
  }

  const filteredProducts = selectedCategory === "Todos"
    ? products
    : products.filter(product => product.category === selectedCategory);

  if (!filteredProducts.length) {
    productsGrid.innerHTML = `
      <div class="empty-state">
        Nenhum produto encontrado nesta categoria.
      </div>
    `;
    return;
  }

  productsGrid.innerHTML = filteredProducts.map(product => `
    <article class="product-card" data-product-details="${product.id}">
      <div class="product-image">
        <img
          src="${escapeHTML(product.image || getDefaultProductImage())}"
          alt="${escapeHTML(product.name)}"
          onerror="this.onerror=null;this.src='images/default-product.svg';"
        />
      </div>

      <div class="product-content">
        <h3 class="product-name">${escapeHTML(product.name)}</h3>
        ${getPresentation(product) ? `<span class="product-presentation">${escapeHTML(getPresentation(product))}</span>` : ""}
        <div class="product-footer">
          <div><strong class="product-price">${escapeHTML(product.price ? formatCurrency(parsePrice(product.price)) : "Preço sob consulta")}</strong></div>
          <button type="button" class="add-to-cart" data-add-to-cart="${product.id}">+ Adicionar</button>
        </div>
      </div>
    </article>
  `).join("");
}

function render() {
  renderCategories();
  renderProducts();
  renderCart();
  updateCartCount();
}

if (categoriesElement) {
  categoriesElement.addEventListener("click", (event) => {
    const categoryButton = event.target.closest("[data-category]");
    if (!categoryButton) return;
    selectCategory(categoryButton.dataset.category);
  });
}

if (productsGrid) {
  productsGrid.addEventListener("click", (event) => {
    const button = event.target.closest("[data-add-to-cart]");
    if (button) {
      event.stopPropagation();
      addToCart(button.dataset.addToCart);
      return;
    }
    const card = event.target.closest("[data-product-details]");
    if (card) openProductDetails(card.dataset.productDetails);
  });
}

if (cartItems) {
  cartItems.addEventListener("click", (event) => {
    const increaseButton = event.target.closest("[data-cart-increase]");
    if (increaseButton) {
      changeQuantity(increaseButton.dataset.cartIncrease, 1);
      return;
    }

    const decreaseButton = event.target.closest("[data-cart-decrease]");
    if (decreaseButton) {
      changeQuantity(decreaseButton.dataset.cartDecrease, -1);
      return;
    }

    const removeButton = event.target.closest("[data-cart-remove]");
    if (removeButton) {
      removeFromCart(removeButton.dataset.cartRemove);
    }
  });
}

if (cartButton) cartButton.addEventListener("click", openCart);
if (heroCartButton) heroCartButton.addEventListener("click", openCart);
if (closeCartButton) closeCartButton.addEventListener("click", closeCart);
if (checkoutButton) checkoutButton.addEventListener("click", handleCheckout);
if (modalAddToCart) modalAddToCart.addEventListener("click", () => {
  if (selectedProductId) addToCart(selectedProductId);
});
if (productModal) productModal.addEventListener("click", event => {
  if (event.target.closest("[data-close-product]")) closeProductDetails();
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape") closeProductDetails();
});

render();

async function loadProducts() {
  try {
    const response = await fetch("products.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const loadedProducts = await response.json();
    if (!Array.isArray(loadedProducts)) throw new Error("Formato inválido");

    products = loadedProducts;
  } catch (error) {
    console.error("Erro ao carregar products.json:", error);
    products = [];
    productsLoadError = true;
  }

  render();
}

loadProducts();
