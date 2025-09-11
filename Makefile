# ==== Config ==========================
APP            ?= meshcore
RG             ?= rg-wf-ia-gpt41
PLAN           ?= asp-meshcore
ACR            ?= meshbrainregistry
IMAGE_NAME     ?= bot-core-wf
IMAGE_TAG      ?= v1.0.0
IMAGE          := $(ACR).azurecr.io/$(IMAGE_NAME):$(IMAGE_TAG)
PORT           ?= 8000
ENV_FILE       ?= .env
PY             ?= python

# ==== Helpers =========================
.PHONY: help
help:
	@echo "Targets:"
	@echo "  dev            - roda Uvicorn local com reload"
	@echo "  lint           - lint (ruff) e formatação (black)"
	@echo "  test           - testes (placeholder)"
	@echo "  docker         - build local da imagem"
	@echo "  run            - roda o container local"
	@echo "  stop           - para o container local"
	@echo "  acr-login      - login no ACR"
	@echo "  push           - push da imagem pro ACR"
	@echo "  deploy         - cria/atualiza WebApp apontando pra imagem"
	@echo "  appsettings    - define App Settings essenciais no WebApp"
	@echo "  logs           - tail dos logs do WebApp"
	@echo "  open           - abre a URL do WebApp no navegador"

# ==== Local ===========================
.PHONY: dev
dev:
	$(PY) -m uvicorn main:app --host 0.0.0.0 --port $(PORT) --reload

.PHONY: lint
lint:
	@$(PY) -m pip install -q ruff black
	ruff check .
	black --check .

.PHONY: test
test:
	@echo "Sem testes configurados ainda. OK."

# ==== Docker ==========================
.PHONY: docker
docker:
	docker build --no-cache -t $(IMAGE_NAME):local .

.PHONY: run
run:
	docker run --rm -p $(PORT):$(PORT) --env-file $(ENV_FILE) --name $(IMAGE_NAME) $(IMAGE_NAME):local

.PHONY: stop
stop:
	- docker stop $(IMAGE_NAME)

# ==== ACR / Azure =====================
.PHONY: acr-login
acr-login:
	az acr login -n $(ACR)

.PHONY: push
push: acr-login
	docker tag $(IMAGE_NAME):local $(IMAGE)
	docker push $(IMAGE)

.PHONY: deploy
deploy:
	# cria o app se não existir (ignora erro se já existe)
	- az webapp create -g $(RG) -p $(PLAN) -n $(APP) --deployment-container-image-name "$(IMAGE)"
	# aponta o app para a imagem do ACR + credenciais
	$(eval USER := $(shell az acr credential show -n $(ACR) --query username -o tsv))
	$(eval PASS := $(shell az acr credential show -n $(ACR) --query passwords[0].value -o tsv))
	az webapp config container set -g $(RG) -n $(APP) \
	  -i "$(IMAGE)" -r "https://$(ACR).azurecr.io" -u "$(USER)" -p "$(PASS)"

.PHONY: appsettings
appsettings:
	az webapp config appsettings set -g $(RG) -n $(APP) --settings \
	  WEBSITES_PORT=$(PORT) \
	  APP_ENV=prod \
	  LOG_FORMAT=json \
	  LOG_LEVEL=INFO

.PHONY: logs
logs:
	az webapp log config -g $(RG) -n $(APP) --application-logging true
	az webapp log tail -g $(RG) -n $(APP)

.PHONY: open
open:
	@start "" https://$(APP).azurewebsites.net/ || xdg-open https://$(APP).azurewebsites.net/ || open https://$(APP).azurewebsites.net/
