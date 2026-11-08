# Настройка NFS-сервера (Rocky Linux 10)

**Зачем это в курсе.** В пособии NFS используется в примерах хранения: PV с `nfs: { server: nfs.local, path: /exports/pv01 }` (модуль 8.8) и StorageClass `nfs-csi` с параметрами `server: nfs.local, share: /exports` (модули 8.8, 9.3). Главное преимущество NFS для Kubernetes — режим **ReadWriteMany (RWX)**: одну шару могут монтировать **несколько подов на разных нодах одновременно** (для облачных дисков это редкость).

Стенд: отдельная ВМ (или та же нода, если места хватает) с Rocky 10, IP из примера — `192.168.56.10`. Все действия — от root (`sudo -i`) или через `sudo`.

## 1. Установка пакетов

```bash
sudo dnf install -y nfs-utils
```

## 2. Каталоги экспорта

```bash
# Каталоги из манифестов пособия: share /exports + подкаталог pv01 (статический PV)
sudo mkdir -p /exports/pv01 /exports/pv02

# Широкие права — для учебного стенда; в проде выставляйте владельца точно (см. шаг 8)
sudo chmod 777 /exports/pv01 /exports/pv02
```

## 3. SELinux (на Rocky включён по умолчанию — пропуск = «Permission denied»)

```bash
sudo dnf install -y policycoreutils-python-utils

# Тип контекста для содержимого, экспортируемого по NFS с записью:
sudo semanage fcontext -a -t public_content_rw_t "/exports(/.*)?"
sudo restorecon -Rv /exports

# Разрешить NFS-серверу экспортировать любые ФС с записью (вклён по умолчанию, проверим явно):
sudo setsebool -P nfs_export_all_rw 1
getsebool nfs_export_all_rw
```

## 4. Экспорты — `/etc/exports`

```bash
sudo tee -a /etc/exports <<'EOF'
/exports/pv01 192.168.56.0/24(rw,sync,no_root_squash,no_subtree_check)
/exports/pv02 192.168.56.0/24(rw,sync,no_root_squash,no_subtree_check)
EOF
```

Параметры и их смысл:
- **`rw`** — чтение и запись;
- **`sync`** — ответ клиенту после записи на диск (надёжность; `async` быстрее, но рискует данными);
- **`no_root_squash`** — root в поде остаётся root'ом на шаре. **Без этого Postgres не сможет `chown` свой каталог данных**, и под будет падать с `Permission denied`. Цена вопроса — клиент с root может испортить всё на шаре: в проде вместо этого выставляют владельца каталога под UID приложения и используют `root_squash` (по умолчанию);
- **`no_subtree_check`** — не проверять, что открытый файл лежит внутри экспортированного дерева (меньше проблем при монтировании подкаталогов).

Применить экспорты без перезапуска:

```bash
sudo exportfs -rav
```

## 5. Firewall (на Rocky активен по умолчанию)

```bash
sudo firewall-cmd --permanent --add-service=nfs
sudo firewall-cmd --permanent --add-service=rpc-bind
sudo firewall-cmd --permanent --add-service=mountd
sudo firewall-cmd --reload
```

NFSv4 (используется по умолчанию) ходит по **порту 2049/tcp**; `rpc-bind` и `mountd` нужны для старых NFSv3-клиентов и диагностики.

## 6. Запуск сервиса и проверка

```bash
sudo systemctl enable --now nfs-server
sudo systemctl status nfs-server --no-pager

sudo exportfs -v                 # что и кому экспортировано
sudo showmount -e localhost      # вид клиента: список шар
```

## 7. Имя `nfs.local` на всех хостах

Манифесты пособия обращаются к серверу по имени **`nfs.local`** — сопоставьте ему IP на **сервере, всех нодах кластера и рабочей машине**:

```bash
echo "192.168.56.10 nfs.local" | sudo tee -a /etc/hosts
```

## 8. Проверка с клиента (с ноды кластера)

```bash
sudo dnf install -y nfs-utils

# Ручное монтирование:
sudo mkdir -p /mnt/nfs-test
sudo mount -t nfs nfs.local:/exports/pv01 /mnt/nfs-test
mount | grep pv01                              # увидеть параметры монтирования
echo "hello from client" | sudo tee /mnt/nfs-test/check.txt
sudo umount /mnt/nfs-test

# Проверка от имени пользователя БД (например, postgres = UID 999):
sudo -u nfsnobody touch /exports/pv01/from-nfsnobody.txt
```

Если `mount` отвечает `Permission denied`, а клиент точно в разрешённой сети — в 90% случаев это **SELinux-контекст** (вернитесь к шагу 3) или `root_squash` там, где приложению нужен `chown` (шаг 4).

Постоянное монтирование (пример для `/etc/fstab`, если шару монтирует сам хост, а не Kubernetes):

```fstab
nfs.local:/exports/pv01  /mnt/nfs-test  nfs  defaults,_netdev  0 0
```

## 9. Привязка к манифестам пособия

### Вариант А — статический PV (как в пособии, модули 8.8/9.3)

Больше ничего ставить не нужно: манифест `08-10-k8s/15-storage-sc-pv-pvc.yaml` (StorageClass + PV + PVC) из `examples/` сразу применяется на этот сервер. Проверка:

```bash
kubectl apply -f examples/08-10-k8s/15-storage-sc-pv-pvc.yaml
kubectl get pv,pvc                          # PV Bound к PVC
kubectl get pod -l app=demo-storage -w      # под дойдёт до Running
```

### Вариант Б — динамическое выделение (PVC без ручных PV)

Для StorageClass `nfs-csi` из пособия нужен провиженер. Самый быстрый на стенде — **nfs-subdir-external-provisioner** (Helm):

```bash
helm repo add nfs-subdir-external-provisioner \
  https://kubernetes-sigs.github.io/nfs-subdir-external-provisioner
helm repo update

helm upgrade --install nfs-provisioner nfs-subdir-external-provisioner/nfs-subdir-external-provisioner \
  --namespace nfs-provisioner --create-namespace \
  --set nfs.server=nfs.local \
  --set nfs.path=/exports \
  --set storageClass.name=nfs-csi \
  --set storageClass.accessModes=ReadWriteMany \
  --set storageClass.allowVolumeExpansion=true \
  --set storageClass.reclaimPolicy=Delete

kubectl -n nfs-provisioner get pods
```

После этого PVC с `storageClassName: nfs-csi` будет создавать подкаталоги `/exports/<pvc-name>` автоматически. **Важно**: provisioner работает с `Delete`-политикой — удаление PVC удаляет данные на шаре; для ценных данных используйте `Retain`-StorageClass (см. модуль 9.3 пособия).

Современная альтернатива — официальный **NFS CSI driver** (`provisioner: nfs.csi.k8s.io`, указан в пособии): даёт снапшоты и расширение томов, но требует больше настройки. Для курса достаточно nfs-subdir.

## 10. Траблшутинг

| Симптом | Причина | Решение |
|---|---|---|
| `mount.nfs: Connection timed out` | Firewall / сеть | Шаг 5, `rpcinfo -p nfs.local`, `nc -zv nfs.local 2049` |
| `mount.nfs: Permission denied` (клиент в нужной сети) | SELinux или `/etc/exports` | Шаги 3–4, `sudo exportfs -v` |
| Под в `Pending`, PVC в `Pending` | PV не создан / класса нет | `kubectl describe pvc`, провиженер запущен (шаг 9Б) |
| Postgres не стартует: `Permission denied` на данных | `root_squash` мешает `chown` | `no_root_squash` (шаг 4) или `chown 999:999 /exports/pv01` |
| Шара «зависла» после ребута сервера | Клиенты не переподключились | `umount -f -l` на клиенте, монтирование с `soft,timeo=30,retrans=3` |
