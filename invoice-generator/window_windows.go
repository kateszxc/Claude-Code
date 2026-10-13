package main

import (
	"os"
	"os/exec"
	"path/filepath"
	"syscall"
	"unsafe"
)

// openWindow prefers Edge (installed on every Windows 10/11 machine), then
// Chrome, in app mode: a plain window with no tabs or address bar.
func openWindow(url string) error {
	var candidates []string
	for _, env := range []string{"ProgramFiles(x86)", "ProgramFiles", "LocalAppData"} {
		dir := os.Getenv(env)
		if dir == "" {
			continue
		}
		candidates = append(candidates,
			filepath.Join(dir, "Microsoft", "Edge", "Application", "msedge.exe"),
			filepath.Join(dir, "Google", "Chrome", "Application", "chrome.exe"),
		)
	}
	for _, exe := range candidates {
		if _, err := os.Stat(exe); err == nil {
			cmd := exec.Command(exe, "--app="+url, "--window-size=1300,950")
			if cmd.Start() == nil {
				return nil
			}
		}
	}
	return exec.Command("rundll32", "url.dll,FileProtocolHandler", url).Start()
}

func showError(msg string) {
	user32 := syscall.NewLazyDLL("user32.dll")
	text, _ := syscall.UTF16PtrFromString(msg)
	title, _ := syscall.UTF16PtrFromString("Invoice Builder")
	const mbIconError = 0x10
	user32.NewProc("MessageBoxW").Call(0,
		uintptr(unsafe.Pointer(text)), uintptr(unsafe.Pointer(title)), mbIconError)
}
