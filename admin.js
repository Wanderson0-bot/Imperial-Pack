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
const productImageFile = document.getElementById("productImageFile");
const productDescription = document.getElementById("productDescription");
const imagePreview = document.getElementById("imagePreview");
const imageHelp = document.getElementById("imageHelp");
const formTitle = document.getElementById("formTitle");

function normalizeImagePath(value) {
  const cleaned = String(value || "").trim();

  if (!cleaned) {
    return "";
  }

  if (/^(https?:)?\/\//i.test(cleaned) || cleaned.startsWith("data:")) {
    return cleaned;
  }

  const normalized = cleaned.replace(/\\/g, "/").replace(/^\.\//, "").replace(/^\/+/, "");

  if (!normalized) {
    return "";
  }

  return normalized.startsWith("images/") ? normalized : `images/${normalized}`;
}

function updateImagePreview(value) {
  const normalized = normalizeImagePath(value);

  if (!normalized) {
    imagePreview.src = "";
    imagePreview.hidden = true;
    return;
  }

  imagePreview.src = normalized;
  imagePreview.hidden = false;
}

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

productImage.addEventListener("input", event => {
  updateImagePreview(event.target.value);
});

productImageFile.addEventListener("change", event => {
  const file = event.target.files && event.target.files[0];

  if (!file) {
    return;
  }

  const suggestedPath = normalizeImagePath(`images/${file.name}`);
  productImage.value = suggestedPath;
  updateImagePreview(suggestedPath);

  imageHelp.textContent = "Arquivo selecionado localmente. Copie este arquivo para a pasta images/ do projeto e confirme o caminho antes de salvar.";
});

form.addEventListener("submit", event => {
  event.preventDefault();

  const product = {
    id: editingId || crypto.randomUUID(),
    name: productName.value.trim(),
    category: productCategory.value,
    price: productPrice.value.trim(),
    image: normalizeImagePath(productImage.value),
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
  productImageFile.value = "";
  productDescription.value = "";
  imagePreview.src = "";
  imagePreview.hidden = true;
  imageHelp.textContent = "Selecione uma imagem no seu computador, copie para a pasta images/ e insira o caminho relativo do arquivo, por exemplo: images/marmita-750.jpg";
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
  productImage.value = normalizeImagePath(product.image || "");
  productDescription.value = product.description;
  productImageFile.value = "";
  updateImagePreview(product.image || "");
  imageHelp.textContent = "Selecione uma imagem no seu computador, copie para a pasta images/ e insira o caminho relativo do arquivo, por exemplo: images/marmita-750.jpg";

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
              src="${escapeHTML(normalizeImagePath(product.image))}"
              alt=""
              onerror="this.onerror=null;this.src='images/default-product.svg';"
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

clearForm();
renderAdminProducts();