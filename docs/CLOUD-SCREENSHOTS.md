# Какие новые скриншоты нужны

Локальные скриншоты из `screenshots/` сохраняются. Для этапа кластера и облака дополнительно нужны:

1. [Успешный GitHub Actions run](https://github.com/xueaaaa/backup-platform-coursework/actions/runs/41404167071): три зелёных задания `test`, `publish`, `deploy`.
2. Развёрнутый шаг `Transfer release and deploy the Swarm stack` задания `deploy`: строки `PASS` копирования/восстановления и двух узлов.
3. `docker node ls` внутреннего Swarm: два узла Ready/Active.
4. `docker stack services coursework-backup-cloud`: пять сервисов `1/1`.
5. `docker stack ps coursework-backup-cloud --filter desired-state=running`: restore-db на worker, остальные сервисы на manager.
6. Облачная панель на `http://localhost:8081`: включённое расписание, архив и журнал cron с `EXIT_CODE=0`.

Команды 3–5 выполняются после SSH-входа на VPS:

```bash
export DOCKER_HOST=tcp://127.0.0.1:23750
docker node ls
docker stack services coursework-backup-cloud
docker stack ps coursework-backup-cloud --filter desired-state=running
```

Панель `localhost:8080` — локальная, `localhost:8081` — облачная через SSH-туннель. Если туннель закрыт, повторно запустите `docs/connect-cloud.ps1` с параметром `-Server` и адресом своего VPS. Облачный пароль указан в локальном `.env.cloud`, параметр `ADMIN_PASSWORD`.

Пароли, приватные ключи, файлы `.env` и `.env.cloud` на скриншоты не включать. Готовые безопасные текстовые подтверждения уже лежат в `docs/evidence/`.

В подписях писать «два учебных узла Swarm внутри одного VPS». Не называть этот стенд двумя физическими серверами или кластером, устойчивым к отказу VPS.
