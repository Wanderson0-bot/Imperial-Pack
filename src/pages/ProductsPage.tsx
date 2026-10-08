import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Header } from '../components/Header';
import { PageHeader } from '../components/PageHeader';
import { categoryService } from '../services/categoryService';
import { productService } from '../services/productService';
import type { Category, Product, ProductStatus } from '../types';

type ProductForm = { name: string; category: string; description: string; price: string; image: string };
type CategoryForm = { name: string; image: string };
const emptyProductForm: ProductForm = { name: '', category: '', description: '', price: '', image: '' };
const emptyCategoryForm: CategoryForm = { name: '', image: '' };

const readFile = (file: File, callback: (value: string) => void) => {
  const reader = new FileReader();
  reader.onload = () => callback(String(reader.result));
  reader.readAsDataURL(file);
};

const statusFor = (stock: number, minimum: number): ProductStatus => stock === 0 ? 'Sem estoque' : stock <= minimum * 0.5 ? 'Crítico' : stock <= minimum ? 'Baixo' : 'Normal';

export function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('Todos');
  const [status, setStatus] = useState('Todos');
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');
  const [feedback, setFeedback] = useState('');
  const [productForm, setProductForm] = useState<ProductForm>(emptyProductForm);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [categoryForm, setCategoryForm] = useState<CategoryForm>(emptyCategoryForm);
  const [editingCategory, setEditingCategory] = useState<Category | null>(null);
  const [showProductForm, setShowProductForm] = useState(false);
  const [showCategoryForm, setShowCategoryForm] = useState(false);

  const loadData = async () => {
    try {
      const [nextProducts, nextCategories] = await Promise.all([productService.getAll(), categoryService.getAll()]);
      setProducts(nextProducts);
      setCategories(nextCategories);
    } catch {
      setErrorMessage('Não foi possível carregar produtos e categorias.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { void loadData(); }, []);

  const filteredProducts = useMemo(() => products.filter((product) => {
    const matchesSearch = `${product.name} ${product.description}`.toLowerCase().includes(search.toLowerCase());
    return matchesSearch && (category === 'Todos' || product.category === category) && (status === 'Todos' || product.status === status);
  }), [products, search, category, status]);

  const openNewProduct = () => { setEditingProduct(null); setProductForm({ ...emptyProductForm, category: categories[0]?.name ?? '' }); setShowProductForm(true); setFeedback(''); };
  const openEditProduct = (product: Product) => { setEditingProduct(product); setProductForm({ name: product.name, category: product.category, description: product.description, price: String(product.price), image: product.image }); setShowProductForm(true); setFeedback(''); };
  const handleImage = (event: ChangeEvent<HTMLInputElement>, callback: (value: string) => void) => { const file = event.target.files?.[0]; if (file) readFile(file, callback); };

  const saveProduct = async (event: FormEvent) => {
    event.preventDefault();
    if (!productForm.name.trim() || !productForm.category || !productForm.description.trim() || Number(productForm.price) <= 0) {
      setFeedback('Preencha nome, categoria, descrição e preço válido.');
      return;
    }
    const base = editingProduct ?? { id: '', cost: 0, margin: 0, markup: 0, stock: 0, minStock: 0, supplier: 'Não informado', status: 'Sem estoque' as ProductStatus, unit: 'un' };
    const price = Number(productForm.price);
    const nextProduct: Product = {
      ...base,
      name: productForm.name.trim(),
      category: productForm.category,
      description: productForm.description.trim(),
      image: productForm.image || '',
      price,
      margin: base.cost ? ((price - base.cost) / price) * 100 : 0,
      markup: base.cost ? ((price - base.cost) / base.cost) * 100 : 0,
      status: statusFor(base.stock, base.minStock),
    };
    try {
      if (editingProduct) await productService.updateProduct(nextProduct);
      else await productService.create(nextProduct);
      setShowProductForm(false);
      setFeedback('Produto salvo com sucesso.');
      await loadData();
    } catch {
      setFeedback('Não foi possível salvar o produto.');
    }
  };

  const removeProduct = async (product: Product) => { if (!window.confirm(`Excluir produto?\n\nTem certeza que deseja excluir ${product.name}?`)) return; try { await productService.remove(product.id); setFeedback('Produto excluído. Histórico relacionado foi preservado.'); await loadData(); } catch { setFeedback('Não foi possível excluir o produto.'); } };

  const saveCategory = async (event: FormEvent) => {
    event.preventDefault();
    if (!categoryForm.name.trim() || (!editingCategory && !categoryForm.image)) { setFeedback('Informe o nome e a imagem da categoria.'); return; }
    try { if (editingCategory) await categoryService.update({ ...editingCategory, name: categoryForm.name.trim(), image: categoryForm.image }); else await categoryService.create({ name: categoryForm.name.trim(), image: categoryForm.image }); setShowCategoryForm(false); setFeedback('Categoria salva com sucesso.'); await loadData(); } catch { setFeedback('Não foi possível salvar a categoria.'); }
  };

  const removeCategory = async (categoryToRemove: Category) => {
    const linked = products.filter((product) => product.category === categoryToRemove.name);
    if (linked.length) { const replacement = window.prompt(`Existem ${linked.length} produto(s) vinculados. Digite o nome de outra categoria para transferi-los ou cancele:`); if (!replacement) return; if (!categories.some((item) => item.name === replacement && item.id !== categoryToRemove.id)) { setFeedback('A categoria de destino não existe. Nenhum dado foi alterado.'); return; } try { await categoryService.remove(categoryToRemove.id, replacement); } catch { setFeedback('Não foi possível excluir a categoria.'); return; } } else if (!window.confirm(`Excluir categoria?\n\nTem certeza que deseja excluir ${categoryToRemove.name}?`)) return; else await categoryService.remove(categoryToRemove.id);
    setFeedback('Categoria excluída. Produtos não foram apagados.'); await loadData();
  };

  return <><Header title="Produtos" breadcrumb="Produtos / Catálogo" /><div className="page-shell"><PageHeader title="Produtos" description="Gerencie produtos, categorias e imagens do catálogo interno." actions={<div className="page-header__actions"><button className="btn btn--secondary" type="button" onClick={() => setShowCategoryForm(true)}>Nova categoria</button><button className="btn btn--primary" type="button" onClick={openNewProduct}>Novo produto</button></div>} />{feedback ? <div className="inline-feedback" role="status">{feedback}</div> : null}<section className="panel"><div className="toolbar"><input placeholder="Buscar produto" value={search} onChange={(event) => setSearch(event.target.value)} /><select value={category} onChange={(event) => setCategory(event.target.value)}><option value="Todos">Todas as categorias</option>{categories.map((item) => <option key={item.id} value={item.name}>{item.name}</option>)}</select><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="Todos">Todos os status</option><option value="Normal">Normal</option><option value="Baixo">Baixo</option><option value="Crítico">Crítico</option><option value="Sem estoque">Sem estoque</option></select></div>{isLoading ? <div className="table-state">Carregando produtos...</div> : errorMessage ? <div className="table-state table-state--error">{errorMessage}</div> : <div className="table-scroll"><table className="table products-table"><thead><tr><th>Produto</th><th>Categoria</th><th>Estoque</th><th>Custo</th><th>Venda</th><th>Margem</th><th>Situação</th><th>Ações</th></tr></thead><tbody>{filteredProducts.length ? filteredProducts.map((product) => <tr key={product.id}><td><Link className="table-product" to={`/produtos/${product.id}`}><span className="table-product__image" style={{ backgroundImage: `url(${product.image})` }} /><span><strong>{product.name}</strong><small>{product.description}</small></span></Link></td><td>{product.category}</td><td>{product.stock} <small className="table-muted">mín. {product.minStock}</small></td><td>R$ {product.cost.toFixed(2)}</td><td>R$ {product.price.toFixed(2)}</td><td>{product.margin.toFixed(1)}%</td><td><span className={`badge badge--${product.status === 'Normal' ? 'success' : product.status === 'Sem estoque' ? 'danger' : 'warning'}`}>{product.status}</span></td><td><div className="table-actions"><button type="button" onClick={() => openEditProduct(product)}>Editar</button><button type="button" className="table-action-danger" onClick={() => void removeProduct(product)}>Excluir</button></div></td></tr>) : <tr><td colSpan={8}><div className="table-state">Nenhum produto encontrado.</div></td></tr>}</tbody></table></div>}</section><section className="panel"><div className="panel__header"><div><h3>Categorias</h3><p className="panel__description">As categorias oficiais podem ser editadas; produtos vinculados nunca são apagados automaticamente.</p></div><button className="btn btn--secondary" type="button" onClick={() => setShowCategoryForm(true)}>Adicionar categoria</button></div><div className="category-admin-grid">{categories.map((item) => <article className="category-admin-card" key={item.id}><div className="category-admin-card__image" style={{ backgroundImage: `url(${item.image})` }} /><div><strong>{item.name}</strong><small>{products.filter((product) => product.category === item.name).length} produto(s)</small></div><div className="table-actions"><button type="button" onClick={() => { setEditingCategory(item); setCategoryForm({ name: item.name, image: item.image }); setShowCategoryForm(true); }}>Editar</button><button type="button" className="table-action-danger" onClick={() => void removeCategory(item)}>Excluir</button></div></article>)}</div></section></div>{showProductForm ? <div className="admin-modal-backdrop"><form className="admin-modal" onSubmit={saveProduct}><div className="admin-modal__header"><div><span className="eyebrow">CATÁLOGO</span><h2>{editingProduct ? 'Editar produto' : 'Novo produto'}</h2></div><button type="button" onClick={() => setShowProductForm(false)} aria-label="Fechar">×</button></div><label>Nome<input required value={productForm.name} onChange={(event) => setProductForm((current) => ({ ...current, name: event.target.value }))} /></label><label>Categoria<select required value={productForm.category} onChange={(event) => setProductForm((current) => ({ ...current, category: event.target.value }))}>{categories.map((item) => <option key={item.id} value={item.name}>{item.name}</option>)}</select></label><label>Descrição<textarea required rows={3} value={productForm.description} onChange={(event) => setProductForm((current) => ({ ...current, description: event.target.value }))} /></label><label>Preço<input required type="number" min="0.01" step="0.01" value={productForm.price} onChange={(event) => setProductForm((current) => ({ ...current, price: event.target.value }))} /></label><label>Imagem do produto<input type="file" accept="image/*" onChange={(event) => handleImage(event, (image) => setProductForm((current) => ({ ...current, image })))} /></label>{productForm.image ? <img className="admin-image-preview" src={productForm.image} alt="Pré-visualização do produto" /> : null}<p className="admin-modal__hint">A imagem é armazenada localmente para esta demonstração e ficará disponível após reabrir o sistema neste navegador.</p>{feedback ? <p className="form-error">{feedback}</p> : null}<div className="admin-modal__actions"><button type="button" className="btn btn--secondary" onClick={() => setShowProductForm(false)}>Cancelar</button><button type="submit" className="btn btn--primary">Salvar produto</button></div></form></div> : null}{showCategoryForm ? <div className="admin-modal-backdrop"><form className="admin-modal" onSubmit={saveCategory}><div className="admin-modal__header"><div><span className="eyebrow">CATÁLOGO</span><h2>{editingCategory ? 'Editar categoria' : 'Nova categoria'}</h2></div><button type="button" onClick={() => { setShowCategoryForm(false); setEditingCategory(null); }} aria-label="Fechar">×</button></div><label>Nome<input required value={categoryForm.name} onChange={(event) => setCategoryForm((current) => ({ ...current, name: event.target.value }))} /></label><label>Imagem da categoria<input type="file" accept="image/*" onChange={(event) => handleImage(event, (image) => setCategoryForm((current) => ({ ...current, image })))} /></label>{categoryForm.image ? <img className="admin-image-preview" src={categoryForm.image} alt="Pré-visualização da categoria" /> : null}<div className="admin-modal__actions"><button type="button" className="btn btn--secondary" onClick={() => { setShowCategoryForm(false); setEditingCategory(null); }}>Cancelar</button><button type="submit" className="btn btn--primary">Salvar categoria</button></div></form></div> : null}</>;
}
