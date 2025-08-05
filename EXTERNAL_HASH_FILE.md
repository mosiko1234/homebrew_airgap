# External Hash File Support

The Homebrew Bottles Sync System supports loading an external hash file on startup to skip downloading bottles that have already been downloaded. This feature is useful for:

- Initial deployment with pre-existing bottle collections
- Migrating from another sync system
- Reducing initial sync time and bandwidth usage
- Disaster recovery scenarios

## Configuration Options

You can configure external hash file support using one of the following methods:

### 1. S3 Key (Same Bucket)

Load an external hash file from the same S3 bucket used for storing bottles:

```hcl
# terraform.tfvars
external_hash_file_s3_key = "external/bottles_hash.json"
```

### 2. S3 Key (Different Bucket)

Load an external hash file from a different S3 bucket:

```hcl
# terraform.tfvars
external_hash_file_s3_key    = "bottles_hash.json"
external_hash_file_s3_bucket = "my-external-bucket"
```

### 3. HTTPS URL

Load an external hash file from any HTTPS URL:

```hcl
# terraform.tfvars
external_hash_file_url = "https://example.com/bottles_hash.json"
```

## Hash File Format

The external hash file must follow this JSON format:

```json
{
  "last_updated": "2025-07-21T03:00:00Z",
  "bottles": {
    "curl-8.0.0-arm64_sonoma": {
      "sha256": "abc123def456789012345678901234567890123456789012345678901234567890",
      "download_date": "2025-07-21",
      "file_size": 1048576
    },
    "wget-1.21.3-arm64_ventura": {
      "sha256": "def456abc789012345678901234567890123456789012345678901234567890123",
      "download_date": "2025-07-20",
      "file_size": 2097152
    }
  }
}
```

### Field Descriptions

- `last_updated`: ISO 8601 timestamp of when the hash file was last updated
- `bottles`: Object containing bottle entries keyed by `{formula}-{version}-{platform}`
- `sha256`: SHA256 hash of the bottle file (64 hexadecimal characters)
- `download_date`: Date when the bottle was downloaded (YYYY-MM-DD format)
- `file_size`: Size of the bottle file in bytes

## Validation and Migration

The system automatically validates external hash files and can migrate them to the current format:

### Validation Checks

- Required fields are present (`bottles`, `last_updated`)
- SHA256 hashes are valid (64 hexadecimal characters)
- Dates are in correct format (YYYY-MM-DD)
- File sizes are positive integers
- Bottle keys follow the expected format

### Automatic Migration

If the external hash file has missing or invalid fields, the system will:

1. Add missing `last_updated` timestamp
2. Add missing `download_date` fields (using current date)
3. Add missing `file_size` fields (using 0 as default)
4. Normalize bottle key formats
5. Skip invalid entries with warnings

## Behavior

### Loading Priority

1. **External Source First**: If configured, the system tries to load the external hash file first
2. **Fallback to Default**: If external loading fails, it falls back to the default `bottles_hash.json` in the main S3 bucket
3. **Empty Start**: If no hash file is found, it starts with an empty hash file

### Merge Strategy

When an external hash file is loaded:

- External entries **overwrite** existing entries with the same bottle key
- The system merges external bottles with any existing bottles
- The `last_updated` timestamp is updated after successful merge

### Error Handling

- **Network Errors**: Logged as warnings, system continues with default hash file
- **Validation Errors**: System attempts migration, logs warnings for invalid entries
- **Corruption**: System falls back to default hash file or starts fresh

## Environment Variables

The following environment variables are automatically set by Terraform:

- `EXTERNAL_HASH_FILE_S3_KEY`: S3 key for external hash file
- `EXTERNAL_HASH_FILE_S3_BUCKET`: S3 bucket for external hash file (optional)
- `EXTERNAL_HASH_FILE_URL`: HTTPS URL for external hash file

## Security Considerations

### S3 Access

- The Lambda and ECS execution roles need read access to the external S3 bucket
- Cross-bucket access requires appropriate IAM policies
- Consider using bucket policies to restrict access

### HTTPS URLs

- Only HTTPS URLs are supported for security
- The system validates SSL certificates
- Consider using signed URLs for private content

### Data Validation

- All external data is validated before use
- Invalid entries are skipped with warnings
- The system never trusts external data without verification

## Examples

### Example 1: Migration from Existing System

If you have an existing bottle collection with a hash file:

```hcl
# terraform.tfvars
external_hash_file_s3_key    = "legacy/bottles_hash.json"
external_hash_file_s3_bucket = "legacy-homebrew-bucket"
```

### Example 2: Shared Hash File

Multiple environments sharing a common hash file:

```hcl
# terraform.tfvars
external_hash_file_url = "https://shared-storage.example.com/bottles_hash.json"
```

### Example 3: Disaster Recovery

Restoring from a backup hash file:

```hcl
# terraform.tfvars
external_hash_file_s3_key = "backups/bottles_hash_20250720.json"
```

## Troubleshooting

### Common Issues

1. **External hash file not found**
   - Check S3 key and bucket names
   - Verify IAM permissions for cross-bucket access
   - Check URL accessibility and SSL certificates

2. **Validation failures**
   - Review CloudWatch logs for specific validation errors
   - Check hash file format against the specification
   - Ensure SHA256 hashes are exactly 64 hexadecimal characters

3. **Performance impact**
   - Large external hash files may increase startup time
   - Consider splitting very large hash files
   - Monitor Lambda timeout settings

### Monitoring

Check CloudWatch logs for:

- `Successfully loaded external hash file` - External file loaded successfully
- `Failed to load external hash file` - External file loading failed
- `Hash file validation failed` - Validation errors found
- `Successfully migrated hash file` - Migration completed

### Testing

To test external hash file functionality:

1. Create a test hash file with a few entries
2. Upload to S3 or make available via HTTPS
3. Configure the external hash file settings
4. Deploy and check logs for successful loading
5. Verify that bottles in the external hash file are skipped during sync

## Limitations

- Only one external hash file source can be configured at a time
- External hash files must be accessible during Lambda/ECS startup
- Very large hash files (>10MB) may impact startup performance
- URL-based hash files require internet connectivity from Lambda/ECS