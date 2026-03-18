import { randomUUID } from "node:crypto";
import "dotenv/config";
import * as bcrypt from "bcrypt";
import { PrismaPg } from "@prisma/adapter-pg";
import { Pool } from "pg";
import {
  ChannelType,
  FriendshipStatus,
  NotificationType,
  PrismaClient,
  UserRole,
  UserStatus,
} from "../node_modules/.prisma/client";

const databaseUrl = process.env.DATABASE_URL;

if (!databaseUrl) {
  throw new Error("DATABASE_URL is required to run prisma seed.");
}

const pool = new Pool({ connectionString: databaseUrl });
const adapter = new PrismaPg(pool);
const prisma = new PrismaClient({ adapter });

async function clearDatabase() {
  await prisma.chatMessage.deleteMany();
  await prisma.channelMember.deleteMany();
  await prisma.channel.deleteMany();
  await prisma.friendship.deleteMany();
  await prisma.notification.deleteMany();
  await prisma.fileUpload.deleteMany();
  await prisma.apiKey.deleteMany();
  await prisma.oAuthAccount.deleteMany();
  await prisma.user.deleteMany();
}

async function seedUsers() {
  const passwordHash = await bcrypt.hash("Passw0rd!", 10);

  const users = [
    {
      email: "admin@transcendence.dev",
      username: "admin",
      displayName: "Admin",
      bio: "Platform administrator",
      role: UserRole.ADMIN,
      status: UserStatus.ONLINE,
      passwordHash,
      is2FAEnabled: true,
      twoFASecret: "TEST_2FA_SECRET",
    },
    {
      email: "alice@transcendence.dev",
      username: "alice",
      displayName: "Alice",
      bio: "Frontend engineer",
      role: UserRole.USER,
      status: UserStatus.ONLINE,
      passwordHash,
    },
    {
      email: "bob@transcendence.dev",
      username: "bob",
      displayName: "Bob",
      bio: "Backend engineer",
      role: UserRole.USER,
      status: UserStatus.BUSY,
      passwordHash,
    },
    {
      email: "charlie@transcendence.dev",
      username: "charlie",
      displayName: "Charlie",
      bio: "QA specialist",
      role: UserRole.USER,
      status: UserStatus.AWAY,
      passwordHash,
    },
    {
      email: "diana@transcendence.dev",
      username: "diana",
      displayName: "Diana",
      bio: "Product manager",
      role: UserRole.USER,
      status: UserStatus.OFFLINE,
      passwordHash,
    },
  ];

  await prisma.user.createMany({ data: users });
  return prisma.user.findMany();
}

async function seedOAuthAccounts(userByUsername: Record<string, string>) {
  await prisma.oAuthAccount.createMany({
    data: [
      {
        provider: "42",
        providerId: "alice-42-id",
        userId: userByUsername.alice,
      },
      {
        provider: "google",
        providerId: "bob-google-id",
        userId: userByUsername.bob,
      },
    ],
  });
}

async function seedFriendships(userByUsername: Record<string, string>) {
  await prisma.friendship.createMany({
    data: [
      {
        requesterId: userByUsername.alice,
        receiverId: userByUsername.bob,
        status: FriendshipStatus.ACCEPTED,
      },
      {
        requesterId: userByUsername.alice,
        receiverId: userByUsername.charlie,
        status: FriendshipStatus.PENDING,
      },
      {
        requesterId: userByUsername.bob,
        receiverId: userByUsername.diana,
        status: FriendshipStatus.BLOCKED,
      },
    ],
  });
}

async function seedChannelsAndMessages(userByUsername: Record<string, string>) {
  const directAliceBob = await prisma.channel.create({
    data: {
      type: ChannelType.DIRECT,
      isPrivate: true,
      members: {
        create: [
          { userId: userByUsername.alice, role: "OWNER" },
          { userId: userByUsername.bob, role: "MEMBER" },
        ],
      },
    },
  });

  const engineering = await prisma.channel.create({
    data: {
      name: "engineering",
      type: ChannelType.PUBLIC,
      members: {
        create: [
          { userId: userByUsername.admin, role: "OWNER" },
          { userId: userByUsername.alice, role: "ADMIN" },
          { userId: userByUsername.bob, role: "MEMBER" },
          { userId: userByUsername.charlie, role: "MEMBER" },
        ],
      },
    },
  });

  const product = await prisma.channel.create({
    data: {
      name: "product",
      type: ChannelType.GROUP,
      isPrivate: true,
      members: {
        create: [
          { userId: userByUsername.diana, role: "OWNER" },
          { userId: userByUsername.admin, role: "ADMIN" },
          { userId: userByUsername.alice, role: "MEMBER" },
        ],
      },
    },
  });

  await prisma.chatMessage.createMany({
    data: [
      {
        channelId: directAliceBob.id,
        senderId: userByUsername.alice,
        content: "Hey Bob, can you review the PR?",
      },
      {
        channelId: directAliceBob.id,
        senderId: userByUsername.bob,
        content: "Sure, I'll check it now.",
      },
      {
        channelId: engineering.id,
        senderId: userByUsername.admin,
        content: "Standup starts in 10 minutes.",
      },
      {
        channelId: engineering.id,
        senderId: userByUsername.charlie,
        content: "QA report is ready for sprint review.",
      },
      {
        channelId: product.id,
        senderId: userByUsername.diana,
        content: "Let's finalize release notes today.",
      },
    ],
  });
}

async function seedNotifications(userByUsername: Record<string, string>) {
  await prisma.notification.createMany({
    data: [
      {
        userId: userByUsername.bob,
        type: NotificationType.FRIEND_REQUEST,
        title: "New friend request",
        message: "Alice sent you a friend request.",
      },
      {
        userId: userByUsername.alice,
        type: NotificationType.FRIEND_ACCEPTED,
        title: "Friend request accepted",
        message: "Bob accepted your friend request.",
        isRead: true,
      },
      {
        userId: userByUsername.charlie,
        type: NotificationType.SYSTEM,
        title: "Maintenance window",
        message: "Scheduled maintenance tonight at 23:00 UTC.",
      },
    ],
  });
}

async function seedFiles(userByUsername: Record<string, string>) {
  await prisma.fileUpload.createMany({
    data: [
      {
        filename: "avatar-alice.png",
        storedName: `${randomUUID()}.png`,
        mimeType: "image/png",
        size: 128_000,
        path: "/uploads/avatars/alice.png",
        userId: userByUsername.alice,
      },
      {
        filename: "qa-report.pdf",
        storedName: `${randomUUID()}.pdf`,
        mimeType: "application/pdf",
        size: 512_600,
        path: "/uploads/docs/qa-report.pdf",
        userId: userByUsername.charlie,
      },
    ],
  });
}

async function seedApiKeys(userByUsername: Record<string, string>) {
  const adminKeyHash = await bcrypt.hash("test-admin-api-key", 10);
  const userKeyHash = await bcrypt.hash("test-alice-api-key", 10);

  await prisma.apiKey.createMany({
    data: [
      {
        name: "Admin integration key",
        keyHash: adminKeyHash,
        userId: userByUsername.admin,
      },
      {
        name: "Alice local dev key",
        keyHash: userKeyHash,
        userId: userByUsername.alice,
      },
    ],
  });
}

async function main() {
  console.log("🧹 Clearing existing data...");
  await clearDatabase();

  console.log("👥 Seeding users...");
  const users = await seedUsers();
  const userByUsername = Object.fromEntries(users.map((user) => [user.username, user.id]));

  console.log("🔐 Seeding OAuth accounts...");
  await seedOAuthAccounts(userByUsername);

  console.log("🤝 Seeding friendships...");
  await seedFriendships(userByUsername);

  console.log("💬 Seeding channels and chat messages...");
  await seedChannelsAndMessages(userByUsername);

  console.log("🔔 Seeding notifications...");
  await seedNotifications(userByUsername);

  console.log("📁 Seeding uploaded files...");
  await seedFiles(userByUsername);

  console.log("🗝️  Seeding API keys...");
  await seedApiKeys(userByUsername);

  console.log("✅ Database seeded successfully.");
}

main()
  .catch((error: unknown) => {
    console.error("❌ Seeding failed:", error);
    process.exitCode = 1;
  })
  .finally(async () => {
    await prisma.$disconnect();
    await pool.end();
  });