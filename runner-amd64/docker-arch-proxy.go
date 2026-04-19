// docker-arch-proxy.go
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httputil"
	"strings"
)

func main() {
	proxy := &httputil.ReverseProxy{
		Director: func(req *http.Request) {
			req.URL.Scheme = "http"
			req.URL.Host  = "docker"
		},
		Transport: &http.Transport{
			DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
				return net.Dial("unix", "/var/run/docker.sock")
			},
		},
		ModifyResponse: func(resp *http.Response) error {
			if !strings.HasSuffix(strings.TrimRight(resp.Request.URL.Path, "/"), "/info") {
				return nil
			}
			body, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			var info map[string]interface{}
			if json.Unmarshal(body, &info) == nil {
				info["Architecture"] = "x86_64"
				body, _              = json.Marshal(info)
			}
			fmt.Println(body)
			resp.Body            = io.NopCloser(bytes.NewReader(body))
			resp.ContentLength   = int64(len(body))
			resp.Header.Set("Content-Length", fmt.Sprintf("%d", len(body)))
			resp.Header.Del("Transfer-Encoding")
			return nil
		},
	}
	ln, err := net.Listen("tcp", "127.0.0.1:2376")
	if err != nil { panic(err) }
	fmt.Println("proxy up on :2376")
	http.Serve(ln, proxy)
}
