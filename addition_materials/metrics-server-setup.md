# Установка metrics-server

**Зачем это в курсе.** В пособии metrics-server нужен в трёх местах: `kubectl top nodes/pods` (модуль 8.7), **HPA** — `kubectl autoscale deployment myapp --cpu-percent=70 --min=2 --max=10` (модуль 8) и графики ресурсов в **Lens/k9s** (модуль 8.6). Без него HPA пишет `failed to get cpu utilization: missing request for cpu`, а `kubectl top` отвечает `metrics not available yet`.

В «голом» кластере (kubeadm, Rocky 10 из §8.5) metrics-server **не ставится автоматически** — ставим сами.

## 1. Установка (официальный манифест)

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

kubectl -n kube-system get pods -l k8s-app=metrics-server -w   # дождаться Running (1/1)
kubectl -n kube-system get deployment metrics-server
```

## 2. Проверка

```bash
kubectl top nodes          # CPU/память каждой ноды
kubectl top pods -A        # по всем подам кластера
kubectl top pods -n staging --sort-by=cpu
```

## 3. Типовая ошибка на bare-metal: `x509: certificate signed by unknown authority`

Kubelet на нодах отдаёт метрики по **самоподписанному сертификату**, а metrics-server по умолчанию его проверяет. Симптом — под metrics-server в Running, но `kubectl top` отвечает ошибкой про сертификат. Лабораторное решение — флаг `--kubelet-insecure-tls`:

```bash
# Через kubectl patch (одной командой):
kubectl -n kube-system patch deployment metrics-server --type='json' -p='[
  {"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}
]'

kubectl -n kube-system rollout status deployment metrics-server
kubectl top nodes        # теперь метрики появляются (~30–60 сек на сбор)
```

Руками то же самое: `kubectl -n kube-system edit deployment metrics-server` → в `spec.template.spec.containers[0].args` добавить строку `--kubelet-insecure-tls`.

> **Это только для стенда.** `--kubelet-insecure-tls` отключает проверку сертификата kubelet'а. Продовый путь: включить для kubelet сертификаты, подписанные CA кластера (kubeadm умеет: `kubelet-certificate-authority` в конфиге control plane), либо выдать kubelet'ам сертификаты от кластерного CA.

## 4. Тот же флаг при установке через Helm

```bash
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
helm repo update

helm upgrade --install metrics-server metrics-server/metrics-server \
  --namespace kube-system \
  --set 'args={--kubelet-insecure-tls}'
```

## 5. Сквозная проверка: HPA из пособия

```bash
# Нужен deployment с заданными resources.requests (иначе нечего считать в процентах):
kubectl apply -f examples/08-10-k8s/05-deployment.yaml

kubectl autoscale deployment myapp --cpu-percent=70 --min=2 --max=10
kubectl get hpa -w
# Цель: столбец TARGETS из <unknown>/70% переходит в 5%/70% — метрики дошли

# Нагрузить можно так (под из того же образа):
kubectl run loadgen --rm -it --image=busybox:1.36 --restart=Never -- \
  sh -c 'while true; do wget -q -O- http://myapp:8000/health >/dev/null; done'
kubectl get hpa -w        # наблюдаем рост TARGETS и потом REPLICAS
kubectl delete hpa myapp  # cleanup
```

## 6. Альтернативы

- **kind**: `kind create cluster` умеет ставить metrics-server автоматически, но сертификаты там самоподписанные — флаг из шага 3 всё равно нужен.
- **k3s**: встроен в дистрибутив, ничего ставить не надо.
- **Prometheus + Prometheus Adapter**: когда нужны не только CPU/память, но и свои метрики (очередь, RPS) для автомасштабирования — тема за пределами курса.
