package com.example.core;
import com.day.cq.replication.Replicator;
import com.google.common.collect.ImmutableList;
import com.day.cq.xss.XSSProtectionService;
import org.apache.commons.lang.StringUtils;
import org.apache.commons.lang3.ObjectUtils;
import org.apache.sling.commons.scheduler.Scheduler;
import org.apache.http.impl.client.HttpClients;
import java.io.FileOutputStream;
import javax.jcr.observation.EventListener;
import com.day.cq.replication.TransportHandler;
public class LegacyService {
  void run() throws Exception {
    // getAdministrativeResourceResolver( in a comment should be ignored
    resolver = factory.getAdministrativeResourceResolver(null);
    try (FileOutputStream fos = new FileOutputStream("/tmp/export.csv")) {}
    client = HttpClients.createDefault();
    Runtime runtime = Runtime.getRuntime();
    runtime.exec("convert in.png out.jpg");
    if (settings.getRunModes().contains("uat")) {}
  }
}
