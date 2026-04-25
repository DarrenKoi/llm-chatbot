# Web Chat (Nuxt SPA)

Cube 장애 대비 웹 fallback 채널의 Nuxt 3 기반 SPA. Flask 서버(`/chat`)에서 정적
서빙되며 `/api/v1/web-chat/*` 엔드포인트를 호출한다.

## 개발

```bash
cd web
npm install
npm run dev    # http://localhost:3000/chat
```

API 호출은 같은 origin이 아니므로 dev 모드에서는 LASTUSER cookie를 수동 주입하거나
Flask CORS를 임시 허용해야 한다. (홈 dev 환경 가이드는 `doc/web_chat_코딩_계획.md` §7 참조)

## 빌드 / 배포

```bash
cd web
npm run build
# .output/public/ 산출물을 api/static/chat/ 으로 복사
```

빌드 산출물은 `.gitignore` 대상이며 운영 배포 시점에 주입한다.
