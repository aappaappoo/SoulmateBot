"""
WeChat Pay integration for subscription payments
"""
import hashlib
import time
import random
import string
import requests
from typing import Dict, Optional
from datetime import datetime
from loguru import logger
from xml.etree import ElementTree as ET

from config import settings


class WeChatPayService:
    """Service for handling WeChat Pay transactions"""
    
    def __init__(self):
        self.app_id = settings.wechat_pay_app_id
        self.mch_id = settings.wechat_pay_mch_id
        self.api_key = settings.wechat_pay_api_key
        self.api_v3_key = settings.wechat_pay_api_v3_key
        self.notify_url = settings.wechat_pay_notify_url
        self.cert_serial_no = settings.wechat_pay_cert_serial_no
        self.private_key_path = settings.wechat_pay_private_key_path
        
        # API endpoints
        self.unified_order_url = "https://api.mch.weixin.qq.com/pay/unifiedorder"
        self.query_order_url = "https://api.mch.weixin.qq.com/pay/orderquery"
    
    def _generate_nonce_str(self, length: int = 32) -> str:
        """Generate random nonce string"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
    def _generate_sign(self, params: Dict[str, str]) -> str:
        """Generate signature for WeChat Pay API"""
        # Sort parameters by key
        sorted_params = sorted(params.items())
        
        # Create string to sign
        string_to_sign = "&".join([f"{k}={v}" for k, v in sorted_params if v])
        string_to_sign += f"&key={self.api_key}"
        
        # Generate MD5 signature
        sign = hashlib.md5(string_to_sign.encode('utf-8')).hexdigest().upper()
        return sign
    
    def _dict_to_xml(self, data: Dict[str, str]) -> str:
        """Convert dictionary to XML format"""
        xml = ["<xml>"]
        for key, value in data.items():
            xml.append(f"<{key}><![CDATA[{value}]]></{key}>")
        xml.append("</xml>")
        return "".join(xml)
    
    def _xml_to_dict(self, xml_str: str) -> Dict[str, str]:
        """Convert XML to dictionary"""
        root = ET.fromstring(xml_str)
        return {child.tag: child.text for child in root}
    
    def create_native_pay_order(
        self,
        order_id: str,
        amount: int,
        description: str,
        user_id: Optional[int] = None
    ) -> Dict[str, any]:
        """
        Create a Native Pay order (QR code payment)
        
        Args:
            order_id: Unique order ID
            amount: Amount in cents (分)
            description: Product description
            user_id: User ID for tracking
            
        Returns:
            Dictionary containing code_url for QR code generation
        """
        try:
            params = {
                "appid": self.app_id,
                "mch_id": self.mch_id,
                "nonce_str": self._generate_nonce_str(),
                "body": description,
                "out_trade_no": order_id,
                "total_fee": str(amount),
                "spbill_create_ip": "8.8.8.8",  # Use a valid public IP or make configurable
                "notify_url": self.notify_url,
                "trade_type": "NATIVE"
            }
            
            # Add signature
            params["sign"] = self._generate_sign(params)
            
            # Convert to XML
            xml_data = self._dict_to_xml(params)
            
            # Send request
            response = requests.post(
                self.unified_order_url,
                data=xml_data.encode('utf-8'),
                headers={"Content-Type": "application/xml"}
            )
            
            # Parse response
            result = self._xml_to_dict(response.text)
            
            if result.get("return_code") == "SUCCESS" and result.get("result_code") == "SUCCESS":
                logger.info(f"✅ WeChat Pay order created: {order_id}")
                return {
                    "success": True,
                    "code_url": result.get("code_url"),
                    "prepay_id": result.get("prepay_id"),
                    "order_id": order_id
                }
            else:
                error_msg = result.get("return_msg") or result.get("err_code_des")
                logger.error(f"WeChat Pay order creation failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }
                
        except Exception as e:
            logger.error(f"Error creating WeChat Pay order: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def create_jsapi_pay_order(
        self,
        order_id: str,
        amount: int,
        description: str,
        openid: str
    ) -> Dict[str, any]:
        """
        Create a JSAPI Pay order (in-app payment)
        
        Args:
            order_id: Unique order ID
            amount: Amount in cents (分)
            description: Product description
            openid: User's WeChat openid
            
        Returns:
            Dictionary containing payment parameters
        """
        try:
            params = {
                "appid": self.app_id,
                "mch_id": self.mch_id,
                "nonce_str": self._generate_nonce_str(),
                "body": description,
                "out_trade_no": order_id,
                "total_fee": str(amount),
                "spbill_create_ip": "8.8.8.8",  # Use a valid public IP or make configurable
                "notify_url": self.notify_url,
                "trade_type": "JSAPI",
                "openid": openid
            }
            
            # Add signature
            params["sign"] = self._generate_sign(params)
            
            # Convert to XML
            xml_data = self._dict_to_xml(params)
            
            # Send request
            response = requests.post(
                self.unified_order_url,
                data=xml_data.encode('utf-8'),
                headers={"Content-Type": "application/xml"}
            )
            
            # Parse response
            result = self._xml_to_dict(response.text)
            
            if result.get("return_code") == "SUCCESS" and result.get("result_code") == "SUCCESS":
                prepay_id = result.get("prepay_id")
                
                # Generate payment parameters for frontend
                timestamp = str(int(time.time()))
                nonce_str = self._generate_nonce_str()
                package = f"prepay_id={prepay_id}"
                
                pay_params = {
                    "appId": self.app_id,
                    "timeStamp": timestamp,
                    "nonceStr": nonce_str,
                    "package": package,
                    "signType": "MD5"
                }
                
                pay_params["paySign"] = self._generate_sign(pay_params)
                
                logger.info(f"✅ WeChat Pay JSAPI order created: {order_id}")
                return {
                    "success": True,
                    "prepay_id": prepay_id,
                    "pay_params": pay_params,
                    "order_id": order_id
                }
            else:
                error_msg = result.get("return_msg") or result.get("err_code_des")
                logger.error(f"WeChat Pay JSAPI order creation failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }
                
        except Exception as e:
            logger.error(f"Error creating WeChat Pay JSAPI order: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def query_order(self, order_id: str) -> Dict[str, any]:
        """
        Query order status
        
        Args:
            order_id: Order ID to query
            
        Returns:
            Dictionary containing order status
        """
        try:
            params = {
                "appid": self.app_id,
                "mch_id": self.mch_id,
                "out_trade_no": order_id,
                "nonce_str": self._generate_nonce_str()
            }
            
            # Add signature
            params["sign"] = self._generate_sign(params)
            
            # Convert to XML
            xml_data = self._dict_to_xml(params)
            
            # Send request
            response = requests.post(
                self.query_order_url,
                data=xml_data.encode('utf-8'),
                headers={"Content-Type": "application/xml"}
            )
            
            # Parse response
            result = self._xml_to_dict(response.text)
            
            if result.get("return_code") == "SUCCESS":
                trade_state = result.get("trade_state")
                return {
                    "success": True,
                    "order_id": order_id,
                    "trade_state": trade_state,
                    "transaction_id": result.get("transaction_id"),
                    "paid": trade_state == "SUCCESS"
                }
            else:
                error_msg = result.get("return_msg")
                logger.error(f"WeChat Pay order query failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }
                
        except Exception as e:
            logger.error(f"Error querying WeChat Pay order: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def verify_notify(self, notify_data: Dict[str, str]) -> bool:
        """
        Verify WeChat Pay notification signature
        
        Args:
            notify_data: Notification data from WeChat Pay
            
        Returns:
            True if signature is valid
        """
        try:
            # Make a copy to avoid mutating the original
            data_copy = notify_data.copy()
            received_sign = data_copy.pop("sign", None)
            if not received_sign:
                return False
            
            # Generate signature
            calculated_sign = self._generate_sign(data_copy)
            
            return received_sign == calculated_sign
            
        except Exception as e:
            logger.error(f"Error verifying WeChat Pay notification: {str(e)}", exc_info=True)
            return False
    
    def get_subscription_amount(self, tier: str) -> int:
        """
        Get subscription amount in cents (分) for a given tier
        
        Args:
            tier: Subscription tier (basic, premium)
            
        Returns:
            Amount in cents
        """
        amounts = {
            "basic": 999,  # 9.99 CNY
            "premium": 1999  # 19.99 CNY
        }
        return amounts.get(tier, 0)
