const defaultProducts = [
  {
    id: crypto.randomUUID(),
    name: "Marmitex de Isopor TM 102 750ml Totalplast",
    category: "Descartáveis",
    price: "",
    image: "",
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
    category: "Delivery",
    price: "",
    image: "",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Lacre de Segurança para Delivery Hambúrguer",
    category: "Delivery",
    price: "",
    image: "",
    description: ""
  },
  {
    id: crypto.randomUUID(),
    name: "Lacre de Segurança para Delivery Simples",
    category: "Delivery",
    price: "",
    image: "",
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

  productsGrid.innerHTML = filteredProducts.map(product => `
    <article class="product-card">

      <div class="product-image">
        ${
          product.image
            ? `<img src="${escapeHTML(product.image)}" alt="${escapeHTML(product.name)}">`
            : `📷<br>Imagem do produto`
        }
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
  `).join("");
}

function render() {
  renderCategories();
  renderProducts();
}

render();