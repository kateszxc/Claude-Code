# Invoice Builder

A single-page invoice editor (`index.html`, `styles.css`, `app.js`). Open
`index.html` in a browser, or run it as a Windows desktop app.

## Windows app

`main.go` bundles the page into one `.exe` with no dependencies. Running it
starts a private server on `127.0.0.1:47821` and opens the page in an
Edge (or Chrome) app window. The app exits on its own about 10 seconds after
the last window closes. Invoices are saved in that browser's storage for
`127.0.0.1:47821`, so they persist between runs.

Build it from this folder (Go 1.22+, any OS):

```sh
GOOS=windows GOARCH=amd64 go build -trimpath -ldflags "-s -w -H windowsgui" -o InvoiceBuilder.exe .
```

The exe is unsigned, so Windows SmartScreen will warn on first launch:
click **More info → Run anyway**.
