# cc-virt-refs

Common Criteria 虚拟化领域结构化资源打包仓库。  
自动从官方源下载标准、PP、认证产品文档、编写指南、学术文献及 GitHub 官方仓库，并按分类打包为 ZIP。

## 快速开始

### 本地运行

```bash
python3 download.py               # 读取 urls.txt，下载并打包为 cc-virt-refs.zip
python3 download.py --nozip       # 仅下载到 artifacts/，不打 ZIP
python3 download.py mylist.txt    # 使用自定义清单
````

### GitHub Actions（推荐）

1. Fork 或推送此仓库到 GitHub。
2. 打开 **Actions** → 选择 **Build CC Virt Refs ZIP** → **Run workflow**。
3. 填写 `tag` 可选（留空只生成 Artifact，填写则自动发布 Release）。
4. 运行完成后，在工作流底部 **Artifacts** 下载 `cc-virt-refs-zip`；若填写了 tag，也可在 **Releases** 页面下载 `cc-virt-refs.zip`。

## urls.txt 格式说明

* 每行一个 URL。
* 以 `#` 开头的行是注释。
* 以 `[分类名]` 开头的行会切换到对应子目录；未指定时默认进入 `00_misc`。
* 支持 `URL -> 自定义路径` 手动指定存放位置（可选）。

示例：

```
[cc-standards]
https://www.commoncriteriaportal.org/files/ccfiles/CC2022PART3R1.pdf

[github-repos]
https://github.com/commoncriteria/virtualization/archive/refs/heads/master.zip
```

## 分类目录

| 分类标记                 | 输出目录                      |
| -------------------- | ------------------------- |
| `cc-standards`       | `00_cc_standards/`        |
| `virtualization-pps` | `01_virtualization_pps/`  |
| `other-pps`          | `02_other_pps/`           |
| `product-examples`   | `03_product_examples/`    |
| `writing-guides`     | `04_writing_guides/`      |
| `research`           | `05_research_literature/` |
| `github-repos`       | `06_github_repos/`        |
| 其他                   | `00_misc/`                |

## 说明

* 个别站点（如 VMware、Oracle）可能有反爬或重定向，下载结果可能为 HTML 索引页而非原始 PDF，属正常现象。
* `artifacts/_status.tsv` 记录每个链接的下载状态，便于排查。
* 所有资源版权归原作者/机构所有，本仓库仅作整理与下载工具，请遵守相关使用条款。
  EOF

echo "[*] 生成 LICENSE..."
cat > LICENSE <<'EOF'
MIT License

Copyright (c) 2026 cc-virt-refs contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
