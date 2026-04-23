// P4-Gate-2 golangci-lint 실증 샘플 — 외부 테스트 리포 PR 에 포함해 분석 결과 검증.
// 의도적 결함:
//   1) gosec G404 — 암호학적으로 안전하지 않은 난수 (math/rand) (security)
//   2) gosec G104 / errcheck — 에러 반환값 무시 (security + code_quality 분류 분기 검증)
//   3) unused — 사용되지 않는 함수 (code_quality)
//   4) staticcheck SA4006 — 값 할당 후 미사용 (code_quality)
package main

import (
	"encoding/json"
	"fmt"
	"math/rand"
)

// unused — 호출되지 않는 함수
func neverCalled() int {
	return 42
}

// G404 — math/rand 암호학적으로 안전 X
func insecureToken() int {
	return rand.Intn(1000000)
}

// errcheck / G104 — 에러 무시
func parseAndPrint(data []byte) {
	var result map[string]interface{}
	json.Unmarshal(data, &result)
	fmt.Println(result)
}

// SA4006 — x 에 할당 후 미사용
func deadStore() int {
	x := 10
	x = 20
	return 0
}

func main() {
	fmt.Println(insecureToken())
	parseAndPrint([]byte(`{"a": 1}`))
	_ = deadStore()
}
