# Google Cloud Storage — fotos do catálogo

O catálogo envia uploads e imagens importadas por URL diretamente ao Google Cloud
Storage quando `GCS_BUCKET` está configurado. Sem essa variável, mantém o armazenamento
legado no Postgres para não quebrar instalações existentes.

## Configuração

1. Crie ou escolha um bucket.
2. Dê à service account usada pelo app permissão para criar, ler e excluir objetos
   (`roles/storage.objectAdmin`) apenas nesse bucket.
3. Configure no app:

```env
GCS_BUCKET=nome-do-bucket
GCS_CREDENTIALS=/code/service-account.json
GCS_PUBLIC_BASE_URL=
```

`GCS_CREDENTIALS` aceita um caminho ou o JSON completo. Se estiver vazio, o app tenta
`GOOGLE_APPLICATION_CREDENTIALS` e depois `GOOGLE_CALENDAR_CREDS`.

O bucket pode continuar privado. Nesse caso, o app gera links V4 assinados por 24 horas
para o painel e para a UAZAPI. Se o bucket ou uma CDN forem públicos, configure
`GCS_PUBLIC_BASE_URL` (por exemplo, `https://storage.googleapis.com/nome-do-bucket`) para
usar links permanentes sem assinatura.

## Uso

- Upload local: Produtos → ícone de imagem.
- Importação: Produtos → ícone de link → um link direto de imagem por linha.
- Preset: itens em `PRESET["produtos"]` podem incluir `"fotos": ["https://..."]`.
  Ao ativar a base com “carregar produtos”, o servidor baixa essas imagens e salva cópias
  no bucket.

São aceitas até 10 URLs por importação e cada imagem pode ter no máximo 12 MB. Ao excluir
uma foto ou produto, o objeto correspondente também é removido do bucket.
