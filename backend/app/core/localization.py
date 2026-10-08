import re
from typing import Any


_API_MESSAGES = {
    'Role already exists.': 'Esta função já existe.',
    'One or more permissions are invalid.': 'Uma ou mais permissões são inválidas.',
    'Only a general administrator can create another general administrator.': 'Somente um administrador geral pode criar outro administrador geral.',
    'Email is already in use.': 'Este e-mail já está em uso.',
    'Unknown role.': 'Função desconhecida.',
    'Supplier name is already registered.': 'Este nome de fornecedor já está cadastrado.',
    'Supplier email is already registered.': 'Este e-mail de fornecedor já está cadastrado.',
    'Supplier phone is already registered.': 'Este telefone de fornecedor já está cadastrado.',
    'A product cannot be linked to a supplier more than once.': 'Um produto não pode ser associado mais de uma vez ao mesmo fornecedor.',
    'One or more active products were not found.': 'Um ou mais produtos ativos não foram encontrados.',
    'End date must be on or after start date.': 'A data final deve ser igual ou posterior à data inicial.',
    'Item discount cannot exceed its gross value.': 'O desconto do item não pode ser maior que o valor bruto.',
    'Active supplier not found.': 'Fornecedor ativo não encontrado.',
    'One or more purchase products no longer exist.': 'Um ou mais produtos da compra não existem mais.',
    'Purchase was already registered or conflicts with an existing record.': 'A compra já foi registrada ou está em conflito com um registro existente.',
    'Only a received purchase can be cancelled.': 'Somente uma compra recebida pode ser cancelada.',
    'A purchase product no longer exists.': 'Um produto da compra não existe mais.',
    'Refund the settled payable before cancelling this purchase.': 'Estorne a conta a pagar liquidada antes de cancelar esta compra.',
    'Purchase stock has already been consumed; cancellation would make inventory inconsistent.': 'O estoque desta compra já foi consumido; o cancelamento deixaria o estoque inconsistente.',
    'A later inventory or cost movement exists; this purchase cannot be safely reversed.': 'Há uma movimentação posterior de estoque ou custo; não é seguro estornar esta compra.',
    'Category name is required.': 'O nome da categoria é obrigatório.',
    'Category already exists.': 'Esta categoria já existe.',
    'Category has linked products; provide a replacement category.': 'Esta categoria possui produtos vinculados; informe uma categoria substituta.',
    'Replacement category not found.': 'Categoria substituta não encontrada.',
    'Unknown product category.': 'Categoria de produto desconhecida.',
    'Pricing approval permission is required to change a product price.': 'É necessária a permissão de aprovação de preços para alterar o preço de um produto.',
    'Price violates configured margin or markup limits.': 'O preço não respeita os limites configurados de margem ou acréscimo sobre o custo.',
    'Price is below the configured minimum margin.': 'O preço está abaixo da margem mínima configurada.',
    'Price exceeds the configured maximum markup.': 'O preço excede o acréscimo máximo sobre o custo configurado.',
    'Active customer not found.': 'Cliente ativo não encontrado.',
    'Customer is already an active partner.': 'Este cliente já é um parceiro ativo.',
    'A custom cycle requires custom_days; choose a supported cycle type.': 'Um ciclo personalizado exige a quantidade de dias; escolha um tipo de ciclo compatível.',
    'Partner customer not found.': 'Cliente parceiro não encontrado.',
    'Prediction not found.': 'Previsão não encontrada.',
    'External order ID is already linked to a different customer.': 'O identificador externo do pedido já está vinculado a outro cliente.',
    'Invalid order status.': 'Status do pedido inválido.',
    'An order product no longer exists.': 'Um produto do pedido não existe mais.',
    'Refund the received amount before cancelling this order.': 'Estorne o valor recebido antes de cancelar este pedido.',
    'Inventory delta must not be zero.': 'A variação do estoque não pode ser zero.',
    'Adjustment would make stock negative.': 'O ajuste deixaria o estoque negativo.',
    'Alert not found.': 'Alerta não encontrado.',
    'Invalid alert status.': 'Status do alerta inválido.',
    'Opportunity not found.': 'Oportunidade não encontrada.',
    'Invalid opportunity status.': 'Status da oportunidade inválido.',
    'DATABASE_URL is not configured.': 'A variável DATABASE_URL não está configurada.',
    'SECRET_KEY is not configured.': 'A variável SECRET_KEY não está configurada.',
    'Invalid or expired session.': 'A sessão é inválida ou expirou.',
    'Initial registration is not configured.': 'O cadastro inicial não está configurado.',
    'This email is not authorized for initial registration.': 'Este e-mail não está autorizado a realizar o cadastro inicial.',
    'Initial registration is already complete.': 'O cadastro inicial já foi concluído.',
    'Invalid credentials or inactive account.': 'Credenciais inválidas ou conta inativa.',
    'Google OAuth is not configured.': 'A autenticação pelo Google não está configurada.',
    'This Google account is not authorized.': 'Esta conta do Google não está autorizada.',
    'No active Imperial Pack account is assigned to this email.': 'Não há uma conta ativa da Imperial Pack associada a este e-mail.',
    'Authentication required.': 'É necessário autenticar-se.',
    'Session is not active.': 'A sessão não está ativa.',
    'Permission denied.': 'Você não tem permissão para realizar esta ação.',
    'Payable payload is required.': 'Os dados da conta a pagar são obrigatórios.',
    'A payable must be settled through its status transition.': 'A conta a pagar deve ser liquidada pela alteração de status.',
    'Receivable payload is required.': 'Os dados da conta a receber são obrigatórios.',
    'A receivable must be settled through its status transition.': 'A conta a receber deve ser liquidada pela alteração de status.',
    'Movement type must be ENTRY or EXIT.': 'O tipo de movimentação deve ser entrada ou saída.',
    'Reference ID is already linked to a different payable.': 'O identificador de referência já está vinculado a outra conta a pagar.',
    'Reference ID is already linked to a different receivable.': 'O identificador de referência já está vinculado a outra conta a receber.',
    'Invalid payable status.': 'Status da conta a pagar inválido.',
    'Only a paid payable can be refunded.': 'Somente uma conta a pagar liquidada pode ser estornada.',
    'Invalid receivable status.': 'Status da conta a receber inválido.',
    'Only a received receivable can be refunded.': 'Somente uma conta a receber recebida pode ser estornada.',
    'Cash movement payload is required.': 'Os dados da movimentação de caixa são obrigatórios.',
    'Unsupported inventory movement type.': 'Tipo de movimentação de estoque não compatível.',
    'One or more inventory products no longer exist.': 'Um ou mais produtos do estoque não existem mais.',
    'Use a single order line per product.': 'Use apenas uma linha por produto no pedido.',
    'Unsupported order source.': 'Origem do pedido não compatível.',
    'Not Found': 'Recurso não encontrado.',
    'Method Not Allowed': 'Método não permitido.',
}

_NOT_FOUND = re.compile(r'^(Active )?(.+?) not found\.$')
_DYNAMIC_MESSAGES = (
    (
        re.compile(r'^Invalid order status transition from (.+) to (.+)\.$'),
        lambda match: f'Não é possível alterar o pedido de {match.group(1)} para {match.group(2)}.',
    ),
    (
        re.compile(r'^Cannot change payable from (.+) to (.+)\.$'),
        lambda match: f'Não é possível alterar a conta a pagar de {match.group(1)} para {match.group(2)}.',
    ),
    (
        re.compile(r'^Cannot change receivable from (.+) to (.+)\.$'),
        lambda match: f'Não é possível alterar a conta a receber de {match.group(1)} para {match.group(2)}.',
    ),
    (
        re.compile(r'^Insufficient stock for product (.+)\.$'),
        lambda match: f'Estoque insuficiente para o produto {match.group(1)}.',
    ),
)
_ENTITY_NAMES = {
    'Product': 'produto',
    'Active product': 'produto ativo',
    'Order': 'pedido',
    'Purchase': 'compra',
    'Customer': 'cliente',
    'Supplier': 'fornecedor',
    'User': 'usuário',
    'Partner': 'parceiro',
    'Active partner': 'parceiro ativo',
    'Alert': 'alerta',
    'Opportunity': 'oportunidade',
    'Prediction': 'previsão',
    'Payable': 'conta a pagar',
    'Receivable': 'conta a receber',
}
_VALIDATION_MESSAGES = {
    'missing': 'Campo obrigatório.',
    'string_type': 'Informe um texto válido.',
    'string_too_short': 'O texto informado é muito curto.',
    'string_too_long': 'O texto informado é muito longo.',
    'int_type': 'Informe um número inteiro válido.',
    'int_parsing': 'Informe um número inteiro válido.',
    'float_type': 'Informe um número válido.',
    'float_parsing': 'Informe um número válido.',
    'decimal_parsing': 'Informe um valor numérico válido.',
    'bool_parsing': 'Informe um valor verdadeiro ou falso.',
    'bool_type': 'Informe um valor verdadeiro ou falso.',
    'date_from_datetime_parsing': 'Informe uma data válida.',
    'datetime_from_date_parsing': 'Informe uma data e hora válidas.',
    'uuid_parsing': 'Informe um identificador válido.',
    'value_error': 'O valor informado é inválido.',
    'extra_forbidden': 'Este campo não é permitido.',
    'greater_than': 'O valor está abaixo do mínimo permitido.',
    'greater_than_equal': 'O valor está abaixo do mínimo permitido.',
    'less_than': 'O valor excede o máximo permitido.',
    'less_than_equal': 'O valor excede o máximo permitido.',
}


def translate_api_message(message: Any) -> Any:
    if not isinstance(message, str):
        return message
    if message in _API_MESSAGES:
        return _API_MESSAGES[message]
    for pattern, translate in _DYNAMIC_MESSAGES:
        match = pattern.match(message)
        if match:
            return translate(match)
    match = _NOT_FOUND.match(message)
    if match:
        qualifier, entity = match.groups()
        entity_name = _ENTITY_NAMES.get(entity)
        if entity_name:
            prefix = 'Ativo ' if qualifier else ''
            return f'{prefix}{entity_name.capitalize()} não encontrado.'
    return message


def translate_validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    translated = []
    for error in errors:
        item = error.copy()
        translation = _VALIDATION_MESSAGES.get(item.get('type'))
        if translation:
            item['msg'] = translation
        translated.append(item)
    return translated
