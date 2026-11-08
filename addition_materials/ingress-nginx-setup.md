# Установка контроллера ingress-nginx

**Зачем это в курсе.** Объекты **Ingress** из модуля 9.2 пособия сами ничего не делают — это декларация маршрутов. Работает их **контроллер**: он читает все Ingress в кластере и программирует reverse proxy. Самый распространённый — **ingress-nginx** (NGINX внутри пода). В облаке провайдер может ставить свой (AWS ALB и т.п.), на нашем bare-metal-стенде (Rocky 10, §8.5) ставим сами.

## 1. Установка через Helm

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

# Bare-metal: вместо LoadBalancer (в «голом» кластере балансировщик не из чего выдать) — NodePort.
# Порты 30080 (http) и 30443 (https) выбраны явно, чтобы не гадать по случайным.
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  --set controller.service.type=NodePort \
  --set controller.service.nodePorts.http=30080 \
  --set controller.service.nodePorts.https=30443

kubectl -n ingress-nginx get pods -w          # контроллер дойдёт до Running
kubectl -n ingress-nginx get svc              # ingress-nginx-controller: 30080:80/TCP, 30443:443/TCP
```

**Альтернатива для однонодового стенда** — режим `hostNetwork: true` (под контроллера висит прямо на портах 80/443 ноды, без NodePort):

```bash
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  --set controller.hostNetwork=true \
  --set controller.service.type=ClusterIP \
  --set dnsPolicy=ClusterFirstWithHostNet
```

## 2. Сквозная проверка Ingress из пособия

```bash
# 1) Приложение и его Service (селектор app=myapp — из манифестов модулей 8–9):
kubectl apply -f examples/08-10-k8s/05-deployment.yaml
kubectl apply -f examples/08-10-k8s/12-service-clusterip.yaml

# 2) Ingress из пособия (examples/08-10-k8s/14-ingress.yaml):
kubectl apply -f examples/08-10-k8s/14-ingress.yaml

# 3) На рабочей машине сопоставляем учебное имя с IP ноды:
echo "192.168.56.11 staging.example.com" | sudo tee -a /etc/hosts

# 4) Проверка (вариант с NodePort):
curl -I http://staging.example.com:30080/health
# Вариант с hostNetwork=true: curl -I http://staging.example.com/health

# 5) Диагностика, если не отвечает:
kubectl describe ingress myapp -n staging   # секция Events: «Successfully synced»?
kubectl logs -n ingress-nginx deploy/ingress-nginx-controller
kubectl get endpoints myapp -n staging      # Service видит поды? (пусто = метки не совпали)
```

## 3. TLS в двух вариантах

**Вариант А — автоматические сертификаты** через cert-manager (инструкция: `addition_materials/cert-manager-setup.md`). В Ingress из пособия уже стоит аннотация `cert-manager.io/cluster-issuer: "letsencrypt-prod"` — после установки cert-manager сертификат появится сам, в `tls.secretName` (Secret `myapp-tls` создаст cert-manager).

**Вариант Б — ручной Secret** (для стенда без публичного DNS, самоподписанный сертификат):

```bash
# Самоподписанный сертификат на учебное имя (только для стенда!):
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout tls.key -out tls.crt -subj "/CN=staging.example.com" \
  -addext "subjectAltName=DNS:staging.example.com"

kubectl create secret tls myapp-tls --cert=tls.crt --key=tls.key -n staging
# имя secret должно совпадать с tls.secretName в Ingress (в манифесте пособия — myapp-tls)

curl -Ik https://staging.example.com:30443/health   # -k: браузер/клиент не доверяет самоподписи — это нормально
```

## 4. Траблшутинг

| Симптом | Где смотреть |
|---|---|
| `404` от NGINX | `kubectl describe ingress` → Events; путь/host не совпали с правилами |
| `503 Service Temporarily Unavailable` | `kubectl get endpoints <svc>` — пусто: метки подов не совпадают с селектором Service |
| Ingress никем не обработан | `ingressClassName: nginx` в манифесте ↔ имя класса от helm-релиза (`kubectl get ingressclass`) |
| Порт не открывается | `kubectl -n ingress-nginx get svc`; firewall ноды (NodePort — диапазон 30000–32767/tcp) |
