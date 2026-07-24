# Blog

이 디렉터리는 WarruruLab을 통해 만들어진 학습 결과물을 Markdown으로 보관하는 공간입니다.

DevTalk에서 학습 대화를 만들고, MCP가 지식 블록으로 구조화하고, DevLog가 초안을 생성하더라도 최종 글은 사람이 검토하고 수정합니다.

> Blog는 AI가 만든 원본 초안 저장소가 아니라, 학습한 내용을 다시 이해하고 정리한 최종 자산 저장소다.

## 역할

- CS, 프레임워크, 인프라 학습 내용을 글로 정리한다.
- WarruruLab 각 서비스의 개발 과정과 설계 결정을 기록한다.
- DevLog가 생성한 초안을 사람이 다듬어 Tistory 기술 블로그 스타일로 보관한다.
- 이후 RAG의 `blog_archive` collection에 넣을 수 있는 고품질 지식 자료가 된다.

## 디렉터리 구조

```text
blog/
├── CS/
│   └── CS, 자료구조, 네트워크, 운영체제 등 학습 글
├── warurulab/
│   ├── devtalk/
│   ├── devlog/
│   ├── mcp/
│   └── rag/
└── README.md
```

## 작성 원칙

- 대화 로그를 그대로 붙이지 않는다.
- 내가 무엇을 몰랐고, 어떻게 이해가 바뀌었는지 남긴다.
- 코드나 설정은 왜 필요한지 함께 설명한다.
- Local LLM 답변은 그대로 믿지 않고, RAG 근거와 공식 문서 기준으로 검토한다.
- 최종 글은 다시 RAG에 넣어도 될 정도로 정리된 형태를 목표로 한다.

## WarruruLab 흐름

```text
DevTalk에서 학습
-> MCP가 knowledge block 생성
-> RAG가 관련 지식 검색
-> DevLog가 블로그 초안 생성
-> 사람이 검토하고 수정
-> blog 디렉터리에 Markdown으로 저장
-> 이후 RAG blog_archive로 재사용
```
