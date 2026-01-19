"""
Tests for WeChat Pay integration
"""
import pytest
from unittest.mock import patch, MagicMock
from src.payment.wechat_pay import WeChatPayService


@pytest.fixture
def wechat_service():
    """Create a test WeChat Pay service"""
    import os
    
    # Set environment variables before importing
    os.environ["WECHAT_PAY_APP_ID"] = "test_app_id"
    os.environ["WECHAT_PAY_MCH_ID"] = "test_mch_id"
    os.environ["WECHAT_PAY_API_KEY"] = "test_api_key"
    os.environ["WECHAT_PAY_API_V3_KEY"] = "test_api_v3_key"
    os.environ["WECHAT_PAY_NOTIFY_URL"] = "https://example.com/notify"
    os.environ["WECHAT_PAY_CERT_SERIAL_NO"] = "test_serial"
    os.environ["WECHAT_PAY_PRIVATE_KEY_PATH"] = "/path/to/key.pem"
    
    # Reload the entire config module
    import sys
    if 'config.settings' in sys.modules:
        del sys.modules['config.settings']
    if 'config' in sys.modules:
        del sys.modules['config']
    
    from src.payment.wechat_pay import WeChatPayService
    service = WeChatPayService()
    yield service


def test_wechat_service_initialization(wechat_service):
    """Test WeChat Pay service initialization"""
    # Service is initialized properly if other tests pass
    assert wechat_service is not None
    assert hasattr(wechat_service, '_generate_nonce_str')
    assert hasattr(wechat_service, '_generate_sign')


def test_generate_nonce_str(wechat_service):
    """Test nonce string generation"""
    nonce = wechat_service._generate_nonce_str()
    
    assert len(nonce) == 32
    assert nonce.isalnum()
    
    # Test custom length
    nonce_short = wechat_service._generate_nonce_str(16)
    assert len(nonce_short) == 16


def test_generate_sign(wechat_service):
    """Test signature generation"""
    params = {
        "appid": "test_app_id",
        "mch_id": "test_mch_id",
        "nonce_str": "test_nonce"
    }
    
    sign = wechat_service._generate_sign(params)
    
    assert isinstance(sign, str)
    assert len(sign) == 32
    assert sign.isupper()


def test_dict_to_xml(wechat_service):
    """Test dictionary to XML conversion"""
    data = {
        "appid": "test_app_id",
        "mch_id": "test_mch_id"
    }
    
    xml = wechat_service._dict_to_xml(data)
    
    assert "<xml>" in xml
    assert "</xml>" in xml
    assert "<appid><![CDATA[test_app_id]]></appid>" in xml
    assert "<mch_id><![CDATA[test_mch_id]]></mch_id>" in xml


def test_xml_to_dict(wechat_service):
    """Test XML to dictionary conversion"""
    xml = """<xml>
        <appid>test_app_id</appid>
        <mch_id>test_mch_id</mch_id>
    </xml>"""
    
    result = wechat_service._xml_to_dict(xml)
    
    assert result["appid"] == "test_app_id"
    assert result["mch_id"] == "test_mch_id"


def test_get_subscription_amount(wechat_service):
    """Test getting subscription amounts"""
    assert wechat_service.get_subscription_amount("basic") == 999
    assert wechat_service.get_subscription_amount("premium") == 1999
    assert wechat_service.get_subscription_amount("unknown") == 0


def test_create_native_pay_order_success(wechat_service):
    """Test creating a native pay order successfully"""
    mock_response = MagicMock()
    mock_response.text = """<xml>
        <return_code><![CDATA[SUCCESS]]></return_code>
        <result_code><![CDATA[SUCCESS]]></result_code>
        <code_url><![CDATA[weixin://wxpay/bizpayurl?pr=test]]></code_url>
        <prepay_id><![CDATA[test_prepay_id]]></prepay_id>
    </xml>"""
    
    with patch("requests.post", return_value=mock_response):
        result = wechat_service.create_native_pay_order(
            order_id="TEST123",
            amount=999,
            description="Test Order"
        )
        
        assert result["success"] is True
        assert "code_url" in result
        assert result["order_id"] == "TEST123"


def test_create_native_pay_order_failure(wechat_service):
    """Test creating a native pay order with failure"""
    mock_response = MagicMock()
    mock_response.text = """<xml>
        <return_code><![CDATA[FAIL]]></return_code>
        <return_msg><![CDATA[Invalid parameters]]></return_msg>
    </xml>"""
    
    with patch("requests.post", return_value=mock_response):
        result = wechat_service.create_native_pay_order(
            order_id="TEST123",
            amount=999,
            description="Test Order"
        )
        
        assert result["success"] is False
        assert "error" in result


def test_query_order_success(wechat_service):
    """Test querying order status successfully"""
    mock_response = MagicMock()
    mock_response.text = """<xml>
        <return_code><![CDATA[SUCCESS]]></return_code>
        <trade_state><![CDATA[SUCCESS]]></trade_state>
        <transaction_id><![CDATA[test_transaction_id]]></transaction_id>
    </xml>"""
    
    with patch("requests.post", return_value=mock_response):
        result = wechat_service.query_order("TEST123")
        
        assert result["success"] is True
        assert result["paid"] is True
        assert result["order_id"] == "TEST123"


def test_query_order_pending(wechat_service):
    """Test querying order status when pending"""
    mock_response = MagicMock()
    mock_response.text = """<xml>
        <return_code><![CDATA[SUCCESS]]></return_code>
        <trade_state><![CDATA[NOTPAY]]></trade_state>
    </xml>"""
    
    with patch("requests.post", return_value=mock_response):
        result = wechat_service.query_order("TEST123")
        
        assert result["success"] is True
        assert result["paid"] is False


def test_verify_notify_valid(wechat_service):
    """Test verifying a valid notification"""
    notify_data = {
        "appid": "test_app_id",
        "mch_id": "test_mch_id",
        "nonce_str": "test_nonce",
        "sign": ""  # Will be generated
    }
    
    # Generate valid signature
    notify_data_copy = notify_data.copy()
    del notify_data_copy["sign"]
    notify_data["sign"] = wechat_service._generate_sign(notify_data_copy)
    
    result = wechat_service.verify_notify(notify_data)
    assert result is True


def test_verify_notify_invalid(wechat_service):
    """Test verifying an invalid notification"""
    notify_data = {
        "appid": "test_app_id",
        "mch_id": "test_mch_id",
        "nonce_str": "test_nonce",
        "sign": "invalid_signature"
    }
    
    result = wechat_service.verify_notify(notify_data)
    assert result is False
