const PRODUCTS_KEY = "imperialProducts";
const CART_KEY = "imperialCart";
const WHATSAPP_NUMBER = "558581942691";

function loadProducts() {
  try {
    const savedProducts = JSON.parse(localStorage.getItem(PRODUCTS_KEY));
    if (Array.isArray(savedProducts) && savedProducts.length > 0) {
      return savedProducts;
    }
  } catch (error) {
    console.warn("Erro ao ler produtos do localStorage:", error);
  }

  const baseProducts = Array.isArray(window.defaultProducts) ? window.defaultProducts : [];
  if (baseProducts.length) {
    localStorage.setItem(PRODUCTS_KEY, JSON.stringify(baseProducts));
  }

  return baseProducts;
}

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

let products = loadProducts();
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

  const categories = ["Todos", "Delivery", "Descartáveis", "Ecológicos", "Acessórios"];
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
    <article class="product-card">
      <div class="product-image">
        <img
          src="${escapeHTML(product.image || getDefaultProductImage())}"
          alt="${escapeHTML(product.name)}"
          onerror="this.onerror=null;this.src='images/default-product.svg';"
        />
      </div>

      <div class="product-content">
        <span class="product-category">${escapeHTML(product.category)}</span>
        <h3 class="product-name">${escapeHTML(product.name)}</h3>
        <p class="product-description">${escapeHTML(product.description || "Produto disponível para atendimento personalizado.")}</p>
        <div class="product-footer">
          <strong class="product-price">${escapeHTML(product.price || "Preço sob consulta")}</strong>
          <button type="button" class="add-to-cart" data-add-to-cart="${product.id}">Adicionar ao carrinho</button>
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
    if (!button) return;
    addToCart(button.dataset.addToCart);
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

render();
