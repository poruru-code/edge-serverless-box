"""
SAM Template Generator Tests (TDD)

テストを先に作成し、実装を後から追加します。
"""

import pytest
import tempfile
from pathlib import Path


class TestSamParser:
    """SAMテンプレートパーサーのテスト"""

    def test_parse_simple_function(self):
        """シンプルな関数定義をパースできる"""
        from tools.generator.parser import parse_sam_template

        sam_content = """
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  HelloFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: lambda-hello
      CodeUri: functions/hello/
      Handler: lambda_function.lambda_handler
      Runtime: python3.12
"""
        result = parse_sam_template(sam_content)
        
        assert len(result['functions']) == 1
        func = result['functions'][0]
        assert func['name'] == 'lambda-hello'
        assert func['code_uri'] == 'functions/hello/'
        assert func['handler'] == 'lambda_function.lambda_handler'
        assert func['runtime'] == 'python3.12'

    def test_parse_function_with_environment(self):
        """環境変数を含む関数をパースできる"""
        from tools.generator.parser import parse_sam_template

        sam_content = """
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  S3TestFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: lambda-s3-test
      CodeUri: functions/s3-test/
      Handler: lambda_function.lambda_handler
      Runtime: python3.12
      Environment:
        Variables:
          S3_ENDPOINT: "http://onpre-storage:9000"
          BUCKET_NAME: "test-bucket"
"""
        result = parse_sam_template(sam_content)
        
        assert len(result['functions']) == 1
        func = result['functions'][0]
        assert func['environment']['S3_ENDPOINT'] == 'http://onpre-storage:9000'
        assert func['environment']['BUCKET_NAME'] == 'test-bucket'

    def test_parse_globals(self):
        """Globalsセクションからデフォルト値を取得できる"""
        from tools.generator.parser import parse_sam_template

        sam_content = """
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Globals:
  Function:
    Runtime: python3.12
    Handler: lambda_function.lambda_handler
    Timeout: 30

Resources:
  HelloFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: lambda-hello
      CodeUri: functions/hello/
"""
        result = parse_sam_template(sam_content)
        
        func = result['functions'][0]
        # Globals から継承
        assert func['runtime'] == 'python3.12'
        assert func['handler'] == 'lambda_function.lambda_handler'

    def test_skip_non_function_resources(self):
        """Function以外のリソースはスキップする"""
        from tools.generator.parser import parse_sam_template

        sam_content = """
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  HelloFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: lambda-hello
      CodeUri: functions/hello/
      Runtime: python3.12
  
  MyLayer:
    Type: AWS::Serverless::LayerVersion
    Properties:
      LayerName: my-layer
      ContentUri: layers/my-layer/
"""
        result = parse_sam_template(sam_content)
        
        # Function のみ抽出
        assert len(result['functions']) == 1
        assert result['functions'][0]['name'] == 'lambda-hello'


class TestDockerfileRenderer:
    """Dockerfileレンダラーのテスト"""

    def test_render_simple_dockerfile(self):
        """シンプルなDockerfileを生成できる"""
        from tools.generator.renderer import render_dockerfile

        func_config = {
            'name': 'lambda-hello',
            'code_uri': 'functions/hello/',
            'handler': 'lambda_function.lambda_handler',
            'runtime': 'python3.12',
            'environment': {},
        }
        
        docker_config = {
            'sitecustomize_source': 'lib/sitecustomize.py',
        }

        result = render_dockerfile(func_config, docker_config)
        
        assert 'FROM public.ecr.aws/lambda/python:3.12' in result
        assert 'COPY lib/sitecustomize.py' in result
        assert 'COPY functions/hello/' in result
        assert 'CMD [ "lambda_function.lambda_handler" ]' in result

    def test_render_dockerfile_with_requirements(self):
        """requirements.txt がある場合 pip install を含む"""
        from tools.generator.renderer import render_dockerfile

        func_config = {
            'name': 'lambda-hello',
            'code_uri': 'functions/hello/',
            'handler': 'lambda_function.lambda_handler',
            'runtime': 'python3.12',
            'environment': {},
            'has_requirements': True,
        }
        
        docker_config = {
            'sitecustomize_source': 'lib/sitecustomize.py',
        }

        result = render_dockerfile(func_config, docker_config)
        
        assert 'pip install -r' in result


class TestFunctionsYmlRenderer:
    """functions.yml レンダラーのテスト"""

    def test_render_functions_yml(self):
        """functions.yml を生成できる"""
        from tools.generator.renderer import render_functions_yml

        functions = [
            {
                'name': 'lambda-hello',
                'environment': {},
            },
            {
                'name': 'lambda-s3-test',
                'environment': {
                    'S3_ENDPOINT': 'http://onpre-storage:9000',
                },
            },
        ]
        
        base_config = {
            'defaults': {
                'environment': {
                    'LAMBDA_ENDPOINT': 'https://onpre-gateway:443',
                    'LOG_LEVEL': '${LOG_LEVEL}',
                },
            },
        }

        result = render_functions_yml(functions, base_config)
        
        assert 'defaults:' in result
        assert 'LAMBDA_ENDPOINT' in result
        assert 'lambda-hello' in result
        assert 'lambda-s3-test' in result
        assert 'S3_ENDPOINT' in result


class TestGeneratorIntegration:
    """ジェネレータ統合テスト"""

    def test_generate_from_sam_template(self):
        """SAMテンプレートからファイルを生成できる"""
        from tools.generator.main import generate_files

        sam_content = """
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Globals:
  Function:
    Runtime: python3.12
    Handler: lambda_function.lambda_handler

Resources:
  HelloFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: lambda-hello
      CodeUri: functions/hello/
"""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # SAMテンプレートを作成
            sam_path = tmpdir / 'template.yaml'
            sam_path.write_text(sam_content)
            
            # 関数ディレクトリを作成
            func_dir = tmpdir / 'functions' / 'hello'
            func_dir.mkdir(parents=True)
            (func_dir / 'lambda_function.py').write_text('def lambda_handler(event, context): pass')
            
            # lib/sitecustomize.py を作成
            lib_dir = tmpdir / 'lib'
            lib_dir.mkdir()
            (lib_dir / 'sitecustomize.py').write_text('# patch')
            
            # 簡易設定
            config = {
                'paths': {
                    'sam_template': str(sam_path),
                    'output_dir': str(tmpdir / 'functions'),
                    'functions_yml': str(tmpdir / 'functions.yml'),
                },
                'docker': {
                    'sitecustomize_source': 'lib/sitecustomize.py',
                },
            }
            
            # 生成実行
            generate_files(config, project_root=tmpdir)
            
            # 検証
            dockerfile = func_dir / 'Dockerfile'
            assert dockerfile.exists(), "Dockerfile should be generated"
            
            functions_yml = tmpdir / 'functions.yml'
            assert functions_yml.exists(), "functions.yml should be generated"
