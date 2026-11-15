package com.example.core;
import com.day.cq.replication.Replicator;
import java.io.FileOutputStream;
public class LegacyService {
  void run() throws Exception {
    // getAdministrativeResourceResolver( in a comment should be ignored
    resolver = factory.getAdministrativeResourceResolver(null);
    try (FileOutputStream fos = new FileOutputStream("/tmp/export.csv")) {}
  }
}
