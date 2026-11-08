# Этап 1: сборка (образ с компилятором — в финал не попадёт), см. пособие 4.9
FROM golang:1.22 AS builder
WORKDIR /src
COPY go.mod ./
RUN go mod download
COPY . .
# Статическая сборка — не нужны библиотеки в рантайме
RUN CGO_ENABLED=0 go build -o /bin/server .

# Этап 2: финальный минимальный образ
FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /bin/server /server
USER nonroot
EXPOSE 8080
ENTRYPOINT ["/server"]
