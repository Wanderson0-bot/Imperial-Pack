const defaultProducts = [
  {
    id: crypto.randomUUID(),
    name: "Marmitex de Isopor TM 102 750ml Totalplast",
    category: "Descartáveis",
    price: "",
    image: "images/produto-exemplo.jpg",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Marmitex de Isopor TM 104 1100ml Totalplast",
    category: "Descartáveis",
    price: "",
    image: "",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Copo PS 200ml Branco Totalplast",
    category: "Descartáveis",
    price: "",
    image: "",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Copo PS Branco 50ml Totalplast",
    category: "Descartáveis",
    price: "",
    image: "",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Guardanapos Flumen 18x20cm",
    category: "Descartáveis",
    price: "",
    image: "",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Papel Acoplado Food 30x38cm",
    category: "Delivery",
    price: "",
    image: "",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Pote para Molho 30ml P-695 Preto",
    category: "Descartáveis",
    price: "",
    image: "",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Pote para Molho 30ml P-695 Branco",
    category: "Descartáveis",
    price: "",
    image: "",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Pote Térmico Descartável MR 300ml sem tampa",
    category: "Descartáveis",
    price: "",
    image: "",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Tampa para Pote MR 200/MR 300ml",
    category: "Descartáveis",
    price: "",
    image: "",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Pote Térmico Descartável MR 500ml",
    category: "Descartáveis",
    price: "",
    image: "",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Tampa para Pote MR 500ml",
    category: "Descartáveis",
    price: "",
    image: "",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Lacre de Segurança para Delivery Açaí",
    category: "Acessórios",
    price: "",
    image: "images/lacre-acai.jpg",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Lacre de Segurança para Delivery Hambúrguer",
    category: "Acessórios",
    price: "",
    image: "images/saco-hamburguer.jpg",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Lacre de Segurança para Delivery Simples",
    category: "Acessórios",
    price: "",
    image: "images/produto-exemplo.jpg",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Papel Alumínio Inoven 30cm 100m",
    category: "Acessórios",
    price: "",
    image: "",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Papel Manteiga 29x50m",
    category: "Acessórios",
    price: "",
    image: "",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Hamburgueira de Isopor",
    category: "Delivery",
    price: "",
    image: "",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Garfo Descartável Extra Forte Branco Plastla",
    category: "Descartáveis",
    price: "",
    image: "",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Colher Descartável Extra Forte Branca Plastlab",
    category: "Descartáveis",
    price: "",
    image: "",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Saco de Hambúrguer Kraft",
    category: "Delivery",
    price: "",
    image: "",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Saco Térmico para Espetinho Delivery",
    category: "Delivery",
    price: "",
    image: "",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Saco para Pastel Simples",
    category: "Delivery",
    price: "",
    image: "",
    description: ""
  }
];

let products = JSON.parse(localStorage.getItem("imperialProducts"));

if (!products || !products.length) {
  products = defaultProducts;
  localStorage.setItem("imperialProducts", JSON.stringify(products));
}

let selectedCategory = "Todos";

const categoriesElement = document.getElementById("categories");
const productsGrid = document.getElementById("productsGrid");

const DEFAULT_IMAGE = "images/default-product.svg";

function normalizeProductImage(value) {
  if (!value || typeof value !== "string") {
    return DEFAULT_IMAGE;
  }

  let cleaned = value.trim();

  if (!cleaned) {
    return DEFAULT_IMAGE;
  }

  if (/^[A-Za-z]:\\/.test(cleaned) || /^[A-Za-z]:\//.test(cleaned)) {
    console.warn("Caminho local de computador ignorado:", cleaned);
    return DEFAULT_IMAGE;
  }

  if (/^(https?:)?\/\//i.test(cleaned) || cleaned.startsWith("data:")) {
    return cleaned;
  }

  cleaned = cleaned.replace(/\\/g, "/");
  cleaned = cleaned.replace(/^\/+/, "");
  cleaned = cleaned.replace(/^\.\//, "");
  cleaned = cleaned.replace(/^imagens\//i, "images/");

  if (!cleaned) {
    return DEFAULT_IMAGE;
  }

  if (cleaned.startsWith("images/images/")) {
    cleaned = cleaned.replace(/^images\/images\//i, "images/");
  }

  if (!cleaned.startsWith("images/")) {
    cleaned = `images/${cleaned}`;
  }

  return cleaned;
}

function getProductImagePath(product) {
  const candidates = [
    product?.image,
    product?.imagem,
    product?.imageUrl,
    product?.imagePath
  ];

  for (const candidate of candidates) {
    const normalized = normalizeProductImage(candidate);

    if (normalized && normalized !== DEFAULT_IMAGE) {
      return normalized;
    }
  }

  return DEFAULT_IMAGE;
}

function escapeHTML(value) {
  return String(value || "").replace(/[&<>"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  }[char]));
}

function renderCategories() {
  const categories = [
    "Todos",
    "Delivery",
    "Descartáveis",
    "Ecológicos",
    "Acessórios"
  ];

  categoriesElement.innerHTML = categories.map(category => `
    <button
      class="category-button ${selectedCategory === category ? "active" : ""}"
      onclick="selectCategory('${category}')"
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

  productsGrid.innerHTML = filteredProducts.map(product => {
    const productImagePath = getProductImagePath(product);
    console.log("caminho final utilizado:", productImagePath);

    return `
      <article class="product-card">
        <div class="product-image">
          <img
            src="${escapeHTML(productImagePath)}"
            alt="${escapeHTML(product.name)}"
            onerror="console.error('Erro ao carregar imagem:', this.src); this.src='images/default-product.svg';"
          >
        </div>

        <div class="product-content">
          <div class="product-category">
            ${escapeHTML(product.category)}
          </div>

          <div class="product-name">
            ${escapeHTML(product.name)}
          </div>

          <div class="product-description">
            ${escapeHTML(product.description || "Descrição do produto")}
          </div>

          <div class="product-price">
            ${escapeHTML(product.price || "Preço sob consulta")}
          </div>

          <a
            class="whatsapp-button"
            href="https://wa.me/558581942691?text=${encodeURIComponent(
              "Olá! Tenho interesse no produto: " + product.name
            )}"
            target="_blank"
          >
            Pedir pelo WhatsApp
          </a>
        </div>
      </article>
    `;
  }).join("");
}

function render() {
  renderCategories();
  renderProducts();
}

render();