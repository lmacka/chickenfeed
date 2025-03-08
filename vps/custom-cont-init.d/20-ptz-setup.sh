#!/usr/bin/with-contenv bash

echo "=== Installing PTZ Camera Control Dependencies ==="

# Install required packages
echo "Installing Python, pip, fcgiwrap, and spawn-fcgi..."
apk add --no-cache python3 py3-pip fcgiwrap spawn-fcgi

# Install Python ONVIF library
echo "Installing Python ONVIF library..."
pip3 install onvif_zeep requests

# Create directories
echo "Creating directories for PTZ control..."
mkdir -p /config/www/cgi-bin/ptz/wsdl
chmod -R 755 /config/www/cgi-bin

# Create a temp directory for Python cache with proper permissions
echo "Creating temp directory for Python cache..."
mkdir -p /config/tmp
chown -R abc:abc /config/tmp
chmod -R 755 /config/tmp

# Create directory for ONVIF schema files - directly where the library expects it
echo "Creating directory for ONVIF schema files..."
mkdir -p /config/www/ver10/schema
chown -R abc:abc /config/www/ver10
chmod -R 755 /config/www/ver10

# Download ONVIF WSDL files if they don't exist
if [ ! -f /config/www/cgi-bin/ptz/wsdl/devicemgmt.wsdl ]; then
    echo "Downloading ONVIF WSDL files..."
    wget -P /config/www/cgi-bin/ptz/wsdl https://www.onvif.org/ver10/device/wsdl/devicemgmt.wsdl
    wget -P /config/www/cgi-bin/ptz/wsdl https://www.onvif.org/ver10/media/wsdl/media.wsdl
    wget -P /config/www/cgi-bin/ptz/wsdl https://www.onvif.org/ver20/ptz/wsdl/ptz.wsdl
    wget -P /config/www/cgi-bin/ptz/wsdl https://www.onvif.org/ver10/schema/onvif.xsd
fi

# Download schema files directly to the expected location
echo "Downloading necessary schema files..."
rm -f /config/www/ver10/schema/onvif.xsd
rm -f /config/www/ver10/schema/common.xsd
wget -P /config/www/ver10/schema https://www.onvif.org/ver10/schema/onvif.xsd
wget -P /config/www/ver10/schema https://www.onvif.org/ver10/schema/common.xsd

# Create a basic xml.xsd file that's often needed
echo "Creating basic XML schema file..."
cat > /config/www/ver10/schema/xml.xsd << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<xs:schema targetNamespace="http://www.w3.org/XML/1998/namespace" 
           xmlns:xs="http://www.w3.org/2001/XMLSchema" 
           xml:lang="en">
  <xs:attribute name="lang" type="xs:language"/>
  <xs:attribute name="space" default="preserve">
    <xs:simpleType>
      <xs:restriction base="xs:NCName">
        <xs:enumeration value="default"/>
        <xs:enumeration value="preserve"/>
      </xs:restriction>
    </xs:simpleType>
  </xs:attribute>
  <xs:attribute name="base" type="xs:anyURI"/>
  <xs:attribute name="id" type="xs:ID"/>
</xs:schema>
EOF

# Set proper permissions for schema files
echo "Setting proper permissions for schema files..."
chown -R abc:abc /config/www/ver10/schema
chmod -R 644 /config/www/ver10/schema/*

# Make all Python scripts executable
chmod +x /config/www/cgi-bin/ptz/*.py 2>/dev/null || true

# Create log file with proper permissions
touch /config/www/cgi-bin/ptz/ptz_log.txt
chown abc:abc /config/www/cgi-bin/ptz/ptz_log.txt
chmod 644 /config/www/cgi-bin/ptz/ptz_log.txt

echo "=== PTZ Camera Control Setup Completed ==="