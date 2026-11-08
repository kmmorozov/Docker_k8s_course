# Установка cert-manager (автоматические TLS-сертификаты)

**Зачем это в курсе.** В манифесте Ingress из модуля 9.2 пособия стоит аннотация `cert-manager.io/cluster-issuer: "letsencrypt-prod"` — это заявка на **автоматический выпуск и продление** TLS-сертификата. Исполняет её **cert-manager**: оператор, который следит за Ingress/Certificate и решает задачу ACME (Let's Encrypt).

## 1. Установка через Helm

```bash
helm repo add jetstack https://charts.jetstack.io
helm repo update

helm upgrade --install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --set crds.enabled=true          # CRD обязательны: без них оператор не увидит своих объектов

kubectl -n cert-manager get pods   # три пода: cert-manager, webhook, cainjector
```

## 2. ClusterIssuer — сначала staging!

Let's Encrypt имеет **staging-окружение** с лоямтными лимитами: пока цепочка не отлажена, работаем против него, иначе можно упереться в лимиты (5 повторных выпусков в неделю на домен) и ждать.

```yaml
# clusterissuer-staging.yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging        # имя должно совпадать с аннотацией в Ingress
spec:
  acme:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    email: you@example.com         # письма о проблемах с сертификатом
    privateKeySecretRef:
      name: letsencrypt-staging    # сюда ACME-клиент сохранит свой аккаунтный ключ
    solvers:
      - http01:                    # проверка: файл по HTTP на 80 порту домена
          ingress:
            class: nginx           # cert-manager временно создаст Ingress для проверки
```

```bash
kubectl apply -f clusterissuer-staging.yaml
kubectl get clusterissuer                 # READY=True
```

Отладились на staging → меняем `server` на боевой `https://acme-v02.api.letsencrypt.org/directory`, имя объекта и secret — на `letsencrypt-prod` (то, что указано в аннотации манифеста из пособия), применяем второй файл.

## 3. Как это работает сквозным примером

```bash
# Ingress из пособия (в нём уже есть аннотация cert-manager.io/cluster-issuer):
kubectl apply -f examples/08-10-k8s/14-ingress.yaml

# Цепочка событий:
# 1. cert-manager видит аннотацию → создаёт объект Certificate
# 2. Certificate → заказ (Order) → challenge HTTP-01
# 3. Создаётся временный Ingress/.well-known/acme-challenge/... — его должен отдать ingress-nginx
# 4. Let's Encrypt проверяет URL из интернета → подписывает → сертификат в Secret myapp-tls
# 5. Ingress подхватывает Secret (поле tls.secretName), продление — автоматически

kubectl get certificate -n staging        # READY=True
kubectl describe certificate myapp-tls -n staging   # цепочка событий при ошибках
kubectl get secret myapp-tls -n staging   # появился тип kubernetes.io/tls
```

## 4. Важное ограничение для учебного стенда

Проверка HTTP-01 требует, чтобы домен **реально резолвился из интернета** и ingress-nginx был на него доступен (порт 80). Для `staging.example.com` на приватной сети (стенд §8.5) выпуск невозможен — варианты:

- **Самоподписанный сертификат вручную**: `addition_materials/ingress-nginx-setup.md`, шаг 3 «Вариант Б»;
- **Внутренний CA**: mkcert на рабочей станции + корень в доверенные;
- **DNS-01 solver** + публичный DNS с API (Yandex Cloud DNS, Route53…) — когда домен ваш, но без входящего HTTP.

## 5. Траблшутинг

| Симптом | Причина |
|---|---|
| `Certificate` в статусе `Pending` долго | Challenge не проходит: домен не резолвится/не доступен извне, лимиты staging |
| Ошибка `urn:ietf:params:acme:error:rateLimited` | Уперлись в лимит Let's Encrypt — переключитесь на staging и подождите |
| `no matches for kind "ClusterIssuer"` | CRD не установлены — переустановите helm-релиз с `--set crds.enabled=true` |
| Сертификат выпустился, браузер ругается | Вы на staging: сертификаты staging-CA браузерам **намеренно** не доверяют — это нормально для отладки |
