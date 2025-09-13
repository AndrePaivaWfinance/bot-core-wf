# Documentação da Infraestrutura

## Visão Geral

Este documento descreve a infraestrutura utilizada para a aplicação, que inclui a utilização de Docker para containerização, Azure Container Registry (ACR) para armazenamento das imagens, e Azure App Service para hospedagem da aplicação. A segurança é garantida através do EasyAuth, e a saúde da aplicação é monitorada via Health Check.

## Fluxo de Deploy

O processo de deploy inicia com a criação da imagem Docker a partir do Dockerfile presente no repositório. Esta imagem é enviada para o Azure Container Registry (ACR). A partir do ACR, o Azure App Service realiza o pull da imagem para realizar o deploy da aplicação em um ambiente gerenciado e escalável.

## Variáveis de Ambiente

As variáveis de ambiente necessárias para o funcionamento da aplicação são configuradas diretamente no Azure App Service. Elas incluem configurações sensíveis e específicas do ambiente, como conexões de banco de dados, chaves de API e parâmetros de configuração.


## Logs e Monitoramento

Os logs da aplicação são coletados pelo Azure App Service e podem ser acessados através do portal do Azure para análise e troubleshooting. O Health Check está configurado para monitorar a saúde da aplicação, garantindo que o serviço esteja sempre disponível e funcionando corretamente.

## Health Check

O endpoint `/healthz` está disponível para monitoramento da saúde da aplicação.

### Como testar manualmente

```bash
curl -v https://meshbrain.azurewebsites.net/healthz
```

### Retorno esperado

```json
{
  "status": "ok",
  "bot": "Mesh",
  "provider_primary": "azure_openai",
  "provider_fallback": "claude",
  "long_term_enabled": false,
  "retrieval_enabled": false,
  "version": "1.0.0"
}
```

Um retorno `200 OK` confirma que o contêiner está rodando corretamente e que os provedores foram carregados.

### Integração com Azure

No Azure App Service, configure o **Health Check** para o caminho `/healthz`. Isso permite que o serviço monitore automaticamente o estado da aplicação e reinicie o contêiner em caso de falhas.

## Pontos de Atenção

- Manter o Dockerfile atualizado conforme as dependências da aplicação evoluem.
- Monitorar o uso do ACR para evitar custos desnecessários com armazenamento.
- Garantir que as variáveis de ambiente estejam sempre corretas e seguras.
- Acompanhar os logs e alertas do Health Check para detectar e corrigir problemas rapidamente.
- Revisar as configurações do EasyAuth para manter a segurança da aplicação.

## Próximos Passos

- Implementar monitoramento mais avançado com alertas automáticos.
- Automatizar o deploy via pipelines CI/CD.
- Revisar e documentar as políticas de segurança relacionadas ao acesso e autenticação.
- Avaliar a escalabilidade da infraestrutura para suportar aumento de carga.
