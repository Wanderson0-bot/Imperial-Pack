let products = JSON.parse(localStorage.getItem("imperialProducts")) || [];

let editingId = null;

const STORAGE_KEY = "imperialProducts";
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

function getImagePath(value) {
  return typeof value === "string" ? value.trim() : "";
}

function setImageMessage(message, isError = false) {
  imageHelp.textContent = message;
  imageHelp.classList.toggle("image-error", isError);
}

function updateImagePreview(value) {
  const imagePath = getImagePath(value);

  imagePreview.onerror = () => {
    imagePreview.hidden = true;
    setImageMessage(`Imagem não encontrada: ${imagePath}. Verifique se o arquivo existe exatamente nesse caminho dentro do projeto.`, true);
  };

  imagePreview.onload = () => {
    imagePreview.hidden = false;
    setImageMessage(`Imagem carregada: ${imagePath}`);
  };

  if (!imagePath) {
    imagePreview.removeAttribute("src");
    imagePreview.hidden = true;
    setImageMessage("Informe o caminho relativo, por exemplo: images/marmita-750.png");
    return;
  }

  if (/^[A-Za-z]:[\\/]/.test(imagePath) || imagePath.startsWith("/") || /^(https?:)?\/\//i.test(imagePath) || imagePath.startsWith("data:")) {
    imagePreview.removeAttribute("src");
    imagePreview.hidden = true;
    setImageMessage("Use somente um caminho relativo do projeto, como images/marmita-750.png. Caminhos do Windows, Base64 e URLs externas não são aceitos.", true);
    return;
  }

  try {
    const imageUrl = new URL(imagePath, document.baseURI);
    imagePreview.src = imageUrl.href;
  } catch (error) {
    imagePreview.removeAttribute("src");
    imagePreview.hidden = true;
    setImageMessage(`Caminho de imagem inválido: ${imagePath}`, true);
    return;
  }

  imagePreview.hidden = false;
  setImageMessage(`Procurando imagem: ${imagePath}`);
}

function saveToStorage() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(products));
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

  const suggestedPath = `images/${file.name}`;
  productImage.value = suggestedPath;
  updateImagePreview(suggestedPath);

  setImageMessage("Arquivo selecionado. Confirme que ele está na pasta images/ do projeto e que o caminho relativo está correto.");
});

form.addEventListener("submit", event => {
  event.preventDefault();

  const imagePath = productImage.value;

  const product = {
    id: editingId || crypto.randomUUID(),
    name: productName.value.trim(),
    category: productCategory.value,
    price: productPrice.value.trim(),
    image: imagePath,
    description: productDescription.value.trim()
  };

  console.log("imagem salva no produto:", product);
  console.log("caminho final utilizado:", imagePath);

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
  imagePreview.removeAttribute("src");
  imagePreview.hidden = true;
  setImageMessage("Informe o caminho relativo, por exemplo: images/marmita-750.png");
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
  productImage.value = getImagePath(product.image);
  productDescription.value = product.description;
  productImageFile.value = "";
  updateImagePreview(product.image);

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
        <img
          class="admin-product-image"
          src="${escapeHTML(product.image || "")}"
          data-image-path="${escapeHTML(product.image || "")}"
          alt=""
        >

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

  adminProductsList.querySelectorAll("img[data-image-path]").forEach(image => {
    const imagePath = image.dataset.imagePath;
    image.onerror = () => {
      image.alt = `Imagem não encontrada: ${imagePath}`;
      image.removeAttribute("src");
    };
  });
}

clearForm();
renderAdminProducts();