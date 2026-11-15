<?php
$path = parse_url($_SERVER["REQUEST_URI"], PHP_URL_PATH);

if ($path !== '/' && file_exists(__DIR__ . $path)) {
    return false; 
}

if ($path === '/api.php') {
    require __DIR__ . '/api.php';
    exit;
}

if ($path === '/') {
    require __DIR__ . '/index.html';
    exit;
}

http_response_code(404);
echo "Not Found";
