IMPERIAL PACK - CATÁLOGO DIGITAL

Arquivos principais:
- index.html = página pública para clientes
- admin.html = painel administrativo para cadastrar e editar produtos
- catalogo.html = arquivo antigo mantido apenas como compatibilidade; redireciona para index.html

Estrutura de imagens locais:
- Crie uma pasta chamada images/ na raiz do projeto.
- Coloque todas as imagens da loja dentro dessa pasta.
- Use caminhos relativos, por exemplo:
  images/marmita-750.jpg
  images/lacre-acai.jpg
  images/saco-hamburguer.jpg
  images/produto-exemplo.jpg

Como nomear as imagens:
- Use nomes simples e em minúsculas.
- Evite espaços e acentos.
- Prefira usar hífen ou underline, por exemplo: marmita-750.jpg, sacola-kraft.jpg.

Como cadastrar uma imagem no painel:
1. Abra admin.html.
2. No formulário do produto, preencha o campo "Caminho da imagem local".
3. Digite o caminho relativo, como images/marmita-750.jpg.
4. Se preferir, selecione a imagem no computador para visualizar uma prévia.
5. Copie o arquivo físico para a pasta images/ do projeto antes de salvar.

Importante sobre upload direto:
- O navegador não consegue enviar arquivos diretamente para o repositório do GitHub/Vercel.
- Por isso, o fluxo correto é: selecionar a imagem no computador, salvar o arquivo na pasta images/ do projeto, confirmar o caminho relativo no painel e salvar o produto.
- O catálogo lê as imagens a partir do caminho do projeto, então elas precisam existir na pasta images/ antes da publicação.

Como enviar imagens para o GitHub:
1. Coloque a nova imagem em images/.
2. Faça commit e push no GitHub.
3. O Vercel detecta a atualização automática e publica o catálogo com as novas imagens.

Como o catálogo funciona:
- Os caminhos são relativos para garantir compatibilidade com Vercel e GitHub Pages.
- Se um produto não tiver imagem, ele usa uma imagem padrão local.
- Se a imagem não existir, a própria aplicação tenta carregar a imagem padrão.

Como testar:
1. Abra admin.html para editar produtos.
2. Abra index.html para visualizar o catálogo.
3. Qualquer referência antiga para catalogo.html será redirecionada automaticamente para index.html.

Observação:
Esta versão continua sem banco de dados e salva os dados no localStorage do navegador. Para sincronizar entre dispositivos, é necessário hospedar a solução com uma base de dados real no futuro.
