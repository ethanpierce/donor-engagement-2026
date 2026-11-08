# Build a static binary, then run it on distroless (no shell, no package manager).
FROM golang:1.27.3 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY *.go ./
COPY public ./public
RUN CGO_ENABLED=0 go build -trimpath -ldflags "-s -w" -o /out/tidepath-portal .

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/tidepath-portal /tidepath-portal
ENV PORT=8080
USER nonroot:nonroot
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD ["/tidepath-portal", "-healthcheck"]
ENTRYPOINT ["/tidepath-portal"]
