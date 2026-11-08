# Приватный Docker Registry (`registry:2`)

**Зачем это в курсе.** §4.7 пособия поднимает реестр для хранения образов внутри компании, а модуль 7 (CI) использует его как **хранилище предыдущих сборок** для кеша `--cache-from`. GitLab имеет встроенный Container Registry (поднят в compose-стенде модуля 6), но отдельный `registry:2` проще для учебных стендов и Docker-модулей.

## 1. Запуск реестра

```bash
# Один контейнер = готовый реестр; данные — в именованном томе (переживает пересоздание)
docker run -d --name registry -p 5000:5000 --restart always \
  -v registry-data:/var/lib/registry \
  registry:2

docker ps --filter name=registry
curl -s http://localhost:5000/v2/        # ответ {} = реестр жив
```

## 2. Доверие клиентов: HTTP без TLS

По умолчанию Docker **отказывается пушить по HTTP** (кроме localhost). Для стенда разрешаем конкретный адрес:

```bash
# /etc/docker/daemon.json на КАЖДОЙ машине-клиенте (раннеры, ноды, рабочая станция)
sudo tee /etc/docker/daemon.json <<'EOF'
{
  "insecure-registries": ["registry.local:5000"]
}
EOF

sudo systemctl restart docker
```

**Имена из пособия**: `localhost:5000` — пуш с той же машины (§4.7), `registry.local:5000` — с других хостов (кеш сборки, модуль 7). Впишите то имя, которым будете пользоваться; если оба — перечислите оба через запятую. Разумеется, имя надо сопоставить с IP: `echo "192.168.56.10 registry.local" | sudo tee -a /etc/hosts`.

> **Прод**: HTTP-регистр в открытой сети — дыра. Для боевого использования ставьте TLS (сертификат + `REGISTRY_HTTP_TLS_CERTIFICATE/KEY` или reverse proxy) либо прячьте реестр в VPN.

## 3. Push / pull / просмотр каталога

```bash
docker tag myapp:1.0 registry.local:5000/myapp:1.0   # имя = <регистр>/<проект>:<тег>
docker push registry.local:5000/myapp:1.0

docker pull registry.local:5000/myapp:1.0

# HTTP API реестра:
curl -s http://registry.local:5000/v2/_catalog                       # список репозиториев
curl -s http://registry.local:5000/v2/myapp/tags/list                # теги образа
```

Тег `latest` в CI удобно двигать: `docker tag myapp:$CI_COMMIT_SHORT_SHA registry.local:5000/myapp:latest && docker push ...` — именно так устроен кеш `--cache-from` в модуле 7.

## 4. Авторизация (опционально, но нужна в «боевом» стенде)

```bash
sudo dnf install -y httpd-tools        # утилита htpasswd (или: openssl passwd -apr1)

mkdir -p ~/registry-auth
htpasswd -Bbn courseuser 'Str0ng!Pass' > ~/registry-auth/htpasswd   # логин/пароль → файл

docker stop registry && docker rm registry
docker run -d --name registry -p 5000:5000 --restart always \
  -v registry-data:/var/lib/registry \
  -v "$HOME/registry-auth:/auth:ro" \
  -e REGISTRY_AUTH=htpasswd \
  -e REGISTRY_AUTH_HTPASSWD_REALM=registry-realm \
  -e REGISTRY_AUTH_HTPASSWD_PATH=/auth/htpasswd \
  registry:2

docker login registry.local:5000       # введите courseuser / Str0ng!Pass
```

Для CI логинятся так: `echo "$REG_PASSWORD" | docker login registry.local:5000 -u "$REG_USER" --password-stdin` (пароль — в **masked variable** GitLab, никогда в коде).

## 5. Запуск через compose (если стенд описан compose-файлом)

```yaml
# registry-docker-compose.yml
services:
  registry:
    image: registry:2
    container_name: registry
    restart: always
    ports:
      - "5000:5000"
    volumes:
      - registry-data:/var/lib/registry
      # с авторизацией добавьте: - ./registry-auth:/auth:ro и те же REGISTRY_AUTH_* из шага 4
volumes:
  registry-data:
```

```bash
docker compose -f registry-docker-compose.yml up -d
```

## 6. Очистка места (важно: реестр только растёт)

По умолчанию удаление образов через API выключено, а место не освобождается само:

```bash
# Разрешить удаление (для нового контейнера добавьте: -e REGISTRY_STORAGE_DELETE_ENABLED=true)
# Удалить манифест тега (digest узнаём из ответа push или через API):
curl -s http://registry.local:5000/v2/myapp/manifests/1.0 \
  -H "Accept: application/vnd.docker.distribution.manifest.v2+json"
# затем: curl -X DELETE http://registry.local:5000/v2/myapp/manifests/<digest>

# Фактическая сборка мусора (запускать после удалений):
docker exec registry bin/registry garbage-collect /etc/docker/registry/config.yml --delete-untagged
```

Практика из курса: в GitLab-регистре хватение чистят политиками (модуль 7), отдельный реестр — регулярным `garbage-collect` по cron.

## 7. Когда переходить на «взрослый» реестр

`registry:2` — хранилище без UI, сканирования уязвимостей и ретеншн-политик. Как только реестр нужен команде — смотрите **Harbor** (open source, полный набор) или используйте **встроенный Container Registry GitLab** (уже поднят в стенде модуля 6: образы по адресу `registry.gitlab.example.com/<group>/<project>`).
