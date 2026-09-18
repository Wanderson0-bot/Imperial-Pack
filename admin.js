let products = JSON.parse(localStorage.getItem("imperialProducts")) || [];

let editingId = null;

const form = document.getElementById("productForm");
const productCount = document.getElementById("productCount");
const adminProductsList = document.getElementById("adminProductsList");

const productId = document.getElementById("productId");
const productName = document.getElementById("productName");
const productCategory = document.getElementById("productCategory");
const productPrice = document.getElementById("productPrice");
const productImage = document.getElementById("productImage");
const productDescription = document.getElementById("productDescription");
const formTitle = document.getElementById("formTitle");

function saveToStorage() {
  localStorage.setItem("imperialProducts", JSON.stringify(products));
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

form.addEventListener("submit", event => {
  event.preventDefault();

  const product = {
    id: editingId || crypto.randomUUID(),
    name: productName.value.trim(),
    category: productCategory.value,
    price: productPrice.value.trim(),
    image: productImage.value.trim(),
    description: productDescription.value.trim()
  };

  if (!product.name) {
    alert("Digite o nome do produto.");
    return;
  }

  if (editingId) {
    products = products.map(item =>
      item.id === editingId ? product : item
    );
  } else {
    products.push(product);
  }

  saveToStorage();
  clearForm();
  renderAdminProducts();

  alert("Produto salvo com sucesso!");
});

function clearForm() {
  editingId = null;
  productId.value = "";
  productName.value = "";
  productCategory.value = "Delivery";
  productPrice.value = "";
  productImage.value = "";
  productDescription.value = "";
  formTitle.textContent = "Adicionar produto";
}

function editProduct(id) {
  const product = products.find(item => item.id === id);

  if (!product) return;

  editingId = id;
  productId.value = product.id;
  productName.value = product.name;
  productCategory.value = product.category;
  productPrice.value = product.price;
  productImage.value = product.image;
  productDescription.value = product.description;

  formTitle.textContent = "Editar produto";

  window.scrollTo({
    top: 0,
    behavior: "smooth"
  });
}

function deleteProduct(id) {
  const product = products.find(item => item.id === id);

  if (!product) return;

  const confirmed = confirm(
    `Deseja excluir "${product.name}"?`
  );

  if (!confirmed) return;

  products = products.filter(item => item.id !== id);

  saveToStorage();
  renderAdminProducts();
}

function renderAdminProducts() {
  productCount.textContent = `${products.length} produtos`;

  if (!products.length) {
    adminProductsList.innerHTML = `
      <p style="color:#667085;font-size:13px">
        Nenhum produto cadastrado.
      </p>
    `;
    return;
  }

  adminProductsList.innerHTML = products.map(product => `
    <div class="admin-product">

      ${
        product.image
          ? `<img
              class="admin-product-image"
              src="${escapeHTML(product.image)}"
              alt=""
            >`
          : `<div class="admin-product-image"></div>`
      }

      <div class="admin-product-info">
        <strong>${escapeHTML(product.name)}</strong>
        <small>
          ${escapeHTML(product.category)}
          •
          ${escapeHTML(product.price || "Preço não definido")}
        </small>
      </div>

      <div class="admin-actions">
        <button
          class="edit-button"
          onclick="editProduct('${product.id}')"
        >
          Editar
        </button>

        <button
          class="delete-button"
          onclick="deleteProduct('${product.id}')"
        >
          Excluir
        </button>
      </div>

    </div>
  `).join("");
}

renderAdminProducts();