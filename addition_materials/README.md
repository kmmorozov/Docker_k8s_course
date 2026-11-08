# Дополнительные материалы курса

Инструкции по настройке **внешних систем**, которые используются в примерах пособия `posobie_devops.md`. Все команды даны для копипаста и проверены на логике курса (стенд: Rocky Linux 10 + kubeadm-кластер из §8.5 пособия).

| Файл | Система | Где используется в пособии |
|---|---|---|
| [nfs-server-setup.md](nfs-server-setup.md) | **NFS-сервер** (Rocky 10) | PV/PVC и StorageClass с `nfs.local` (модули 8.8, 9.3) |
| [docker-registry-setup.md](docker-registry-setup.md) | **Приватный Docker Registry** (`registry:2`) | §4.7, кеш сборки в CI (модуль 7) |
| [metrics-server-setup.md](metrics-server-setup.md) | **metrics-server** | `kubectl top`, HPA (модули 8, 10) |
| [ingress-nginx-setup.md](ingress-nginx-setup.md) | **контроллер ingress-nginx** | Ingress (модуль 9.2) |
| [cert-manager-setup.md](cert-manager-setup.md) | **cert-manager** | автоматический TLS в Ingress (модуль 9.2) |

Порядок работы: ставьте систему **до** запуска связанных с ней манифестов из пособия. Имена хостов (`nfs.local`, `registry.local`, `staging.example.com`) — учебные, совпадают с манифестами; сопоставьте их своим IP в `/etc/hosts` (показано в каждой инструкции).
