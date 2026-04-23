// SPDX-License-Identifier: UNLICENSED
// P4-Gate slither 실증 샘플 — 외부 테스트 리포 PR 에 포함해 분석 결과 검증.
// 의도적 결함 3건:
//   1) reentrancy-eth (HIGH) — 외부 호출 후 상태 변경
//   2) tx-origin (MEDIUM) — tx.origin 인증
//   3) weak-prng (MEDIUM) — block.timestamp/difficulty 기반 난수
// pragma ^0.8.0 는 Railway buildCommand 사전 설치 solc 0.8.20 과 호환.
pragma solidity ^0.8.0;

contract Vulnerable {
    mapping(address => uint) public balances;

    function withdraw(uint amount) external {
        require(balances[msg.sender] >= amount, "insufficient");
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
        balances[msg.sender] -= amount;
    }

    function isOwner(address owner) external view returns (bool) {
        return tx.origin == owner;
    }

    function rand() external view returns (uint) {
        return uint(keccak256(abi.encodePacked(block.timestamp, block.difficulty)));
    }

    receive() external payable {
        balances[msg.sender] += msg.value;
    }
}
