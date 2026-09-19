let products = [];
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
const adminStatus = document.getElementById("adminStatus");
const exportProductsButton = document.getElementById("exportProductsButton");

function getImagePath(value) {
  return typeof value === "string" ? value.trim() : "";
}

function setImageMessage(message, isError = false) {
  if (!imageHelp) return;
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

function setAdminStatus(message, isError = false) {
  if (!adminStatus) return;
  adminStatus.textContent = message;
  adminStatus.classList.toggle("image-error", isError);
}

function exportProducts() {
  const file = new Blob([`${JSON.stringify(products, null, 2)}\n`], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(file);
  link.download = "products.json";
  link.click();
  URL.revokeObjectURL(link.href);
  setAdminStatus("products.json exportado. Substitua o arquivo no projeto e faça commit/push no GitHub.");
}

function escapeHTML(value) {
  return String(value || "").replace(/[&<>\"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  }[char]));
}

if (productImage) {
  productImage.addEventListener("input", event => {
    updateImagePreview(event.target.value);
  });
}

if (productImageFile) {
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
}

if (form) {
  form.addEventListener("submit", event => {
    event.preventDefault();

    const imagePath = productImage ? productImage.value : "";
    const product = {
      id: editingId || crypto.randomUUID(),
      name: productName.value.trim(),
      category: productCategory.value,
      price: productPrice.value.trim(),
      image: imagePath,
      description: productDescription.value.trim()
    };

    if (!product.name) {
      alert("Digite o nome do produto.");
      return;
    }

    if (editingId) {
      products = products.map(item => item.id === editingId ? product : item);
    } else {
      products.push(product);
    }

    clearForm();
    renderAdminProducts();
    setAdminStatus("Alteração feita apenas nesta sessão. Baixe products.json para publicar no GitHub.");
  });
}

function clearForm() {
  editingId = null;
  if (productId) productId.value = "";
  if (productName) productName.value = "";
  if (productCategory) productCategory.value = "Delivery";
  if (productPrice) productPrice.value = "";
  if (productImage) productImage.value = "";
  if (productImageFile) productImageFile.value = "";
  if (productDescription) productDescription.value = "";
  if (imagePreview) {
    imagePreview.removeAttribute("src");
    imagePreview.hidden = true;
  }
  setImageMessage("Informe o caminho relativo, por exemplo: images/marmita-750.png");
  if (formTitle) formTitle.textContent = "Adicionar produto";
}

function editProduct(id) {
  const product = products.find(item => item.id === id);
  if (!product) return;

  editingId = id;
  if (productId) productId.value = product.id;
  if (productName) productName.value = product.name;
  if (productCategory) productCategory.value = product.category;
  if (productPrice) productPrice.value = product.price;
  if (productImage) productImage.value = getImagePath(product.image);
  if (productDescription) productDescription.value = product.description;
  if (productImageFile) productImageFile.value = "";
  updateImagePreview(product.image);

  if (formTitle) formTitle.textContent = "Editar produto";

  window.scrollTo({ top: 0, behavior: "smooth" });
}

function deleteProduct(id) {
  const product = products.find(item => item.id === id);
  if (!product) return;

  const confirmed = confirm(`Deseja excluir "${product.name}"?`);
  if (!confirmed) return;

  products = products.filter(item => item.id !== id);
  renderAdminProducts();
  setAdminStatus("Produto excluído apenas nesta sessão. Baixe products.json para publicar no GitHub.");
}

function renderAdminProducts() {
  if (!productCount || !adminProductsList) return;

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
          <button class="edit-button" type="button" onclick="editProduct('${product.id}')">Editar</button>
          <button class="delete-button" type="button" onclick="deleteProduct('${product.id}')">Excluir</button>
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

if (exportProductsButton) exportProductsButton.addEventListener("click", exportProducts);

async function loadProducts() {
  try {
    const response = await fetch("products.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const loadedProducts = await response.json();
    if (!Array.isArray(loadedProducts)) throw new Error("Formato inválido");

    products = loadedProducts;
    renderAdminProducts();
    setAdminStatus("Produtos carregados de products.json. As alterações ficam nesta sessão até a exportação.");
  } catch (error) {
    console.error("Erro ao carregar products.json:", error);
    setAdminStatus("Não foi possível carregar products.json. Nenhuma lista local foi usada.", true);
    renderAdminProducts();
  }
}

loadProducts();
