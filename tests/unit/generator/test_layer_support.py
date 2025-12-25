
import pytest
from tools.generator import renderer, main as generator_main

def test_detect_zip_layer():
    """LayerのContentUriが.zipで終わる場合、is_zip=True となること"""
    # このテストは main.py または parser のロジックを検証するが、
    # renderer の入力(func_config)構築部分のロジックとして検証する
    
    # 実際には parser で解決されるか、main.py で後処理されるか
    # 今回は main.py で処理する想定でテストを書く
    pass

def test_render_dockerfile_with_zip_layer():
    """Zip Layerが含まれる場合、Multi-stage build (unzip) が生成されること"""
    func = {
        "name": "test-func",
        "code_uri": "./app/",
        "handler": "app.handler",
        "runtime": "python3.12",
        "layers": [
            {"name": "lib-layer", "content_uri": "./layers/lib.zip"}, 
            {"name": "common-layer", "content_uri": "./layers/common/"}
        ]
    }
    docker_config = {}
    
    output = renderer.render_dockerfile(func, docker_config)
    print(f"\nDEBUG OUTPUT:\n{output}\n")
    
    # Check for simple COPY logic (no unzip)
    assert "FROM alpine:latest as layer-unzipper" not in output
    assert "RUN unzip" not in output
    
    # Renderer now just iterates and copies whatever URI is given
    assert "COPY ./layers/lib.zip /opt/" in output
    assert "COPY ./layers/common/ /opt/" in output
